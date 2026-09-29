from __future__ import annotations
import io
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

import numpy as np
from PIL import Image

from engine5_confidence.calibration import ConfidenceCalibrator
from engine5_confidence.evidence import extract_evidence
from engine5_confidence.fusion import LogisticFusion,row_from_evidence
from engine5_confidence.pipeline import ConfidencePipeline
from engine5_confidence.reliability import reliability_bins,write_reliability_png
from engine5_confidence.schemas import Detection
from engine6_geolocation.adapters import NavigationAdapter,SimulatedLocationAdapter,SubPipeAdapter
from engine6_geolocation.association import associate_timestamp
from engine6_geolocation.coordinates import validate_coordinates
from engine6_geolocation.schemas import NavigationFix
from engine6_geolocation.service import GeolocationService
from engine7_evaluation.artifacts import write_artifacts
from engine7_evaluation.leakage import check_leakage
from engine7_evaluation.manifest import load_tile_manifest,split_records
from engine7_evaluation.metrics import evaluate_detections
from engine8_api.detector import MockDetector
from engine8_api.server import handler_for
from engine8_api.service import AnalysisService
from engine4_detector import YOLODetector
from engine10_ghostnet.generate import generate as generate_ghostnet


def png_bytes():
    # Synthetic images are test fixtures only; never used as project data/results.
    image=Image.fromarray(np.tile(np.arange(64,dtype=np.uint8),(48,1)))
    output=io.BytesIO(); image.save(output,format="PNG"); return output.getvalue()


def detection(image, bbox=(18,10,32,30), source="TEST_FIXTURE"):
    h,w=image.shape[:2]
    return Detection("fixture-1","fixture-image",0,"fixture_class",__import__("engine5_confidence.schemas",fromlist=["BBox"]).BBox(*bbox),0.63,w,h,source,{"test_fixture":True})


class Engine5Tests(unittest.TestCase):
    def test_features_and_boundary_bbox_are_finite(self):
        image=np.tile(np.arange(64,dtype=np.uint16),(48,1))
        result=extract_evidence(image,detection(image,(-3,10,12,50)))
        self.assertTrue(result["shadow_diagnostics"]["valid"])
        self.assertGreaterEqual(result["normalized_area"],0)
        self.assertLessEqual(result["local_contrast"],1)

    def test_invalid_bbox_and_dimension_mismatch_fail_closed(self):
        image=np.zeros((10,10),dtype=np.uint8)
        result=extract_evidence(image,detection(image,(1,1,1.5,1.5)))
        self.assertIsNone(result["shadow_consistency"])
        with self.assertRaises(ValueError): extract_evidence(image,detection(image,(1,1,3,3)).__class__("d","i",0,"c",detection(image).bbox,0.2,9,9))

    def test_pipeline_schema_stays_uncalibrated_until_fitted(self):
        image=np.tile(np.arange(64,dtype=np.uint8),(48,1))
        row=ConfidencePipeline().score(image,detection(image)).to_dict()
        self.assertEqual(row["confidence_status"],"UNCALIBRATED")
        self.assertIsNone(row["calibrated_confidence"])
        self.assertEqual(row["raw_confidence"],0.63)
        self.assertIn("FUSION_MODEL_UNAVAILABLE",row["reason_codes"])

    def test_fitted_fusion_and_calibrator_produce_separate_calibrated_value(self):
        image=np.tile(np.arange(64,dtype=np.uint8),(48,1)); det=detection(image)
        features=extract_evidence(image,det); vector=row_from_evidence(det.raw_confidence,features)
        rows=[vector[:],vector[:],vector[:],vector[:],vector[:],vector[:]]
        rows[0][0]=.1; rows[1][0]=.2; rows[2][0]=.3; rows[3][0]=.7; rows[4][0]=.8; rows[5][0]=.9
        model=LogisticFusion().fit(rows,[0,0,0,1,1,1],iterations=100)
        scores=[model.predict_score(row) for row in rows]
        calibrator=ConfidenceCalibrator().fit(scores,[0,0,0,1,1,1],split_name="calibration")
        result=ConfidencePipeline(fusion=model,calibrator=calibrator).score(image,det).to_dict()
        self.assertEqual(result["confidence_status"],"CALIBRATED")
        self.assertIsNotNone(result["calibrated_confidence"])

    def test_fusion_fit_persist_load(self):
        x=[[.1,.1,.1,0,.01],[.2,.2,.2,.2,.02],[.8,.8,.8,.5,.1],[.9,.9,.9,.7,.2],[.15,.3,.1,.1,.01],[.85,.7,.8,.6,.15]]
        model=LogisticFusion().fit(x,[0,0,1,1,0,1],iterations=300)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"fusion.json"; model.save(path); loaded=LogisticFusion.load(path)
            self.assertGreater(loaded.predict_score(x[2]),loaded.predict_score(x[0]))
        with self.assertRaises(ValueError): LogisticFusion().fit(x,[1]*6)

    def test_calibration_requires_dedicated_split_and_persists(self):
        calibrator=ConfidenceCalibrator("isotonic")
        with self.assertRaises(ValueError): calibrator.fit([.1,.2,.8,.9],[0,0,1,1],split_name="test")
        calibrator.fit([.1,.2,.8,.9],[0,0,1,1],split_name="calibration",sample_ids=["a","b","c","d"],evaluation_ids={"z"})
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"cal.json"; calibrator.save(path); loaded=ConfidenceCalibrator.load(path)
            self.assertGreater(loaded.transform(.9),loaded.transform(.1))

    def test_reliability_bins_and_png(self):
        bins=reliability_bins([.1,.2,.85,.95],[0,0,1,1],4)
        self.assertEqual(sum(row["count"] for row in bins),4)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"reliability.png"; write_reliability_png(bins,path); self.assertGreater(path.stat().st_size,100)


class Engine6Tests(unittest.TestCase):
    def test_coordinate_validation(self):
        self.assertEqual(validate_coordinates("12.2","-77"),(12.2,-77.0))
        for pair in [(91,0),(0,181),(None,2),(float("nan"),0),("bad",0)]:
            with self.subTest(pair=pair),self.assertRaises(ValueError): validate_coordinates(*pair)

    def test_missing_and_matched_navigation(self):
        service=GeolocationService()
        unavailable=service.locate(image_id="i",object_class="pipe",bbox=[0,0,1,1],confidence=None,source_dataset="AI4Shipwrecks")
        self.assertEqual(unavailable.geolocation_type,"Unavailable"); self.assertIsNone(unavailable.latitude)
        for source in ("AI4Shipwrecks","MILCO/NOMBO"):
            no_fix=service.locate(image_id="image",object_class="contact",bbox=[0,0,1,1],confidence=None,source_dataset=source)
            self.assertEqual(no_fix.geolocation_type,"Unavailable"); self.assertIsNone(no_fix.longitude)
        fix=NavigationFix("2026-01-01T00:00:00Z",10,20,"verified.csv")
        match,reason=associate_timestamp("2026-01-01T00:00:00.5Z",[fix],tolerance_seconds=1)
        self.assertIsNotNone(match)
        mismatch,reason=associate_timestamp("2026-01-01T00:00:03Z",[fix],tolerance_seconds=1)
        self.assertIsNone(mismatch); self.assertIn("tolerance",reason)

    def test_adapter_absent_and_simulated_explicit(self):
        self.assertEqual(SubPipeAdapter(None).load_fixes(),[])
        with tempfile.TemporaryDirectory() as td:
            adapter=NavigationAdapter(Path(td)/"missing.csv"); self.assertEqual(adapter.load_fixes(),[])
        result=SimulatedLocationAdapter().locate(1,2)
        self.assertEqual(result["geolocation_type"],"Simulated")

    def test_navigation_csv_requires_actual_coordinates(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"nav.csv"; path.write_text("timestamp,latitude,longitude\n2026-01-01T00:00:00Z,12,34\n")
            self.assertEqual(len(NavigationAdapter(path).load_fixes()),1)
            bad=Path(td)/"bad.csv"; bad.write_text("timestamp,x,y\n1,2,3\n")
            self.assertEqual(NavigationAdapter(bad).load_fixes(),[])


class Engine7Tests(unittest.TestCase):
    def test_group_split_and_no_invented_grouping(self):
        rows=[{"image_id":str(i),"source_dataset":"A","survey":f"S{i//3}"} for i in range(12)]
        split,info=split_records(rows,seed=7)
        self.assertEqual(info["group_key"],"survey")
        self.assertTrue(all(len({r["split"] for r in split if r["survey"]==survey})==1 for survey in {r["survey"] for r in split}))
        split2,info2=split_records([{"image_id":"i","source_dataset":"A"}])
        self.assertEqual(info2["group_key"],"image_id"); self.assertIn("Not available",info2["limitation"])

    def test_duplicate_and_tile_leakage_detection(self):
        records=[{"image_id":"a","image_path":"missing","original_image_id":"orig","tile_bbox":[0,0,20,20],"split":"train"},
                 {"image_id":"b","image_path":"missing","original_image_id":"orig","tile_bbox":[10,10,30,30],"split":"test"},
                 {"image_id":"a","image_path":"missing","split":"val"}]
        report=check_leakage(records); kinds={issue["type"] for issue in report["issues"]}
        self.assertIn("duplicate_image_id",kinds); self.assertIn("original_image_tiles_cross_splits",kinds); self.assertIn("overlapping_tiles_cross_splits",kinds)

    def test_actual_dataset_builder_manifest_adapter(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); manifest=root/"manifest.csv"
            manifest.write_text("tile,split,source,orig_image,x,y,n_boxes\ntile-a,train,ai4shipwrecks_train,wreck-01.png,0,0,1\ntile-b,test,ai4shipwrecks_train,wreck-01.png,320,0,1\n")
            rows=load_tile_manifest(manifest,tile_size=640)
            self.assertEqual(rows[0]["tile_bbox"],[0,0,640,640])
            report=check_leakage(rows)
            self.assertTrue(any(issue["type"]=="overlapping_tiles_cross_splits" for issue in report["issues"]))
            self.assertIsNone(rows[0].get("survey"))

    def test_metrics_are_computed_only_when_called_with_records(self):
        result=evaluate_detections([{"image_id":"i","class_id":0,"bbox":[0,0,10,10]}],[{"image_id":"i","class_id":0,"bbox":[0,0,10,10],"confidence":.9}],["pipe"])
        self.assertEqual(result["mAP@0.5"],1.0); self.assertEqual(result["per_class"]["pipe"]["recall"],1.0)

    def test_artifacts_skip_project_metrics_when_not_provided(self):
        with tempfile.TemporaryDirectory() as td:
            result=write_artifacts([],[],td)
            self.assertFalse(result["metrics_written"])
            self.assertTrue((Path(td)/"leakage_report.json").is_file())
            self.assertFalse((Path(td)/"metrics.json").exists())
            self.assertIn("Not available with current metadata",(Path(td)/"generalization_report.md").read_text())


class Engine4Tests(unittest.TestCase):
    def test_yolo_adapter_merges_overlapping_tile_predictions(self):
        class Tensor:
            def __init__(self, values): self.values=values
            def cpu(self): return self
            def tolist(self): return self.values
        class Boxes:
            def __init__(self,box):
                self.xyxy=Tensor([box]); self.cls=Tensor([0]); self.conf=Tensor([.8])
        class Result:
            def __init__(self,box): self.boxes=Boxes(box)
        class Model:
            names={0:"pipe",1:"shipwreck",2:"mine_like",3:"crab_pot"}
            calls=0
            def predict(self,**kwargs):
                self.calls+=1
                box=[500,100,640,200] if self.calls==1 else [340,100,480,200]
                return [Result(box)]
        result=YOLODetector("unused.pt",model=Model(),tile_size=640,overlap=160).analyze(
            np.zeros((500,800,3),dtype=np.uint8),image_id="image",source_dataset="SubPipe")
        self.assertEqual(len(result),1)
        self.assertEqual(result[0].class_name,"Pipe")
        self.assertEqual(result[0].bbox.to_list(),[500.0,100.0,640.0,200.0])
        self.assertEqual(len(result[0].provenance["tile_origins"]),2)

    def test_yolo_adapter_rejects_wrong_class_taxonomy(self):
        class Model: names={0:"Ghost Net"}
        with self.assertRaises(ValueError): YOLODetector("unused.pt",model=Model())


class Engine10Tests(unittest.TestCase):
    def test_ghostnet_generation_is_separate_and_background_grouped(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); backgrounds=root/"backgrounds"; backgrounds.mkdir()
            for index in range(5):
                Image.fromarray(np.full((96,128),40+index,dtype=np.uint8)).save(backgrounds/f"bg-{index}.png")
            output=root/"experimental"
            report=generate_ghostnet(backgrounds,output,count=10,seed=4)
            self.assertEqual(report["status"],"SYNTHETIC_EXPERIMENT_ONLY")
            self.assertTrue(report["synthetic_test_available"])
            self.assertEqual(len(list((output/"images"/"synthetic_test").glob("*.png"))),2)
            self.assertTrue((output/"data.yaml").is_file())
            manifest=(output/"manifest.csv").read_text()
            self.assertIn("experimental_ghost_net",manifest)
            self.assertIn("background_image",manifest)


class Engine8Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.store=Path(self.temp.name)/"reviews.json"
        self.service=AnalysisService(detector=MockDetector(),review_store=self.store)
        self.http=ThreadingHTTPServer(("127.0.0.1",0),handler_for(self.service)); self.thread=threading.Thread(target=self.http.serve_forever,daemon=True); self.thread.start()
        self.base=f"http://127.0.0.1:{self.http.server_port}"

    def tearDown(self): self.http.shutdown(); self.http.server_close(); self.thread.join(); self.temp.cleanup()

    def request(self,path,method="GET",data=None,headers=None):
        req=Request(self.base+path,data=data,headers=headers or {},method=method)
        try:
            with urlopen(req) as response: return response.status,response.read(),response.headers.get("Content-Type")
        except HTTPError as error: return error.code,error.read(),error.headers.get("Content-Type")

    def test_health_and_upload_mock_end_to_end(self):
        status,body,_=self.request("/api/health"); self.assertEqual(status,200); self.assertEqual(json.loads(body)["mode"],"MOCK")
        status,body,_=self.request("/api/analyze","POST",png_bytes(),{"Content-Type":"image/png","X-Filename":"fixture.png","X-Source-Dataset":"ALL"})
        result=json.loads(body); self.assertEqual(status,200); self.assertIn("MOCK",result["message"])
        self.assertEqual(result["datasets"],["AI4Shipwrecks","MILCO/NOMBO","SubPipe","PINGEcosystem"])
        self.assertEqual({item["source_dataset"] for item in result["detections"]},set(result["datasets"]))
        self.assertEqual(len(result["detections"]),4)

    def test_injected_test_detector_flows_through_engines_5_and_6(self):
        # This detector and its prediction exist only as a synthetic test fixture.
        class TestDetector:
            mode="MOCK"
            def analyze(self,image,*,image_id,source_dataset):
                from engine5_confidence.schemas import BBox
                return [Detection("test-only",image_id,0,"test_class",BBox(5,5,24,28),.6,image.shape[1],image.shape[0],source_dataset,{"test_fixture":True})]
        service=AnalysisService(detector=TestDetector(),review_store=self.store)
        # Direct injected test service verifies the adapter boundary and
        # complete scoring/geolocation chain for a single selected dataset.
        result=service.analyze_bytes(png_bytes(),source_dataset="MILCO/NOMBO")
        detection_result=result["detections"][0]
        self.assertEqual(result["mode"],"MOCK")
        self.assertEqual(detection_result["confidence_status"],"UNCALIBRATED")
        self.assertIsNone(detection_result["calibrated_confidence"])
        self.assertEqual(detection_result["geolocation_type"],"Unavailable")
        self.assertIsNone(detection_result["latitude"]); self.assertIsNone(detection_result["longitude"])

    def test_real_detector_does_not_duplicate_one_image_per_dataset(self):
        class RealDetector:
            mode="REAL"
            calls=0
            def analyze(self,image,*,image_id,source_dataset):
                self.calls+=1
                return [detection(image,source=source_dataset)]
        detector=RealDetector()
        service=AnalysisService(detector=detector,review_store=self.store)
        result=service.analyze_bytes(png_bytes(),source_dataset="ALL")
        self.assertEqual(detector.calls,1)
        self.assertEqual(result["datasets"],["UNKNOWN"])
        self.assertEqual(len(result["detections"]),1)
        self.assertEqual(result["detections"][0]["source_dataset"],"UNKNOWN")

    def test_review_persistence_and_exports(self):
        payload=json.dumps({"detection_id":"review-fixture","action":"flag","note":"synthetic test fixture"}).encode()
        self.assertEqual(self.request("/api/review","POST",payload,{"Content-Type":"application/json"})[0],200)
        self.assertEqual(json.loads(self.store.read_text())["review-fixture"]["status"],"flag")
        self.assertEqual(self.request("/api/export?format=json")[0],200)
        self.assertIn(b"review-fixture",self.request("/api/reviews")[1])
        self.assertIn(b"detection_id",self.request("/api/export?format=csv")[1])

    def test_invalid_image_rejected(self):
        status,body,_=self.request("/api/analyze","POST",b"not image",{"Content-Type":"image/png"})
        self.assertEqual(status,400); self.assertIn(b"invalid",body)

    def test_unconfigured_dataset_rejected(self):
        status,body,_=self.request("/api/analyze","POST",png_bytes(),{"Content-Type":"image/png","X-Source-Dataset":"made-up"})
        self.assertEqual(status,400); self.assertIn(b"unsupported source dataset",body)

    def test_review_requires_object_and_string_fields(self):
        status,body,_=self.request("/api/review","POST",b"[]",{"Content-Type":"application/json"})
        self.assertEqual(status,400); self.assertIn(b"JSON object",body)
        payload=json.dumps({"detection_id":[],"action":"confirm","note":""}).encode()
        status,body,_=self.request("/api/review","POST",payload,{"Content-Type":"application/json"})
        self.assertEqual(status,400); self.assertIn(b"must be strings",body)


if __name__=="__main__": unittest.main()
