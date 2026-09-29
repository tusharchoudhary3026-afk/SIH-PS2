"""Detection metrics at IoU 0.5 for explicitly supplied prediction/GT records."""
from __future__ import annotations
from collections import Counter


def iou(a,b):
    x1,y1=max(a[0],b[0]),max(a[1],b[1]); x2,y2=min(a[2],b[2]),min(a[3],b[3])
    inter=max(0,x2-x1)*max(0,y2-y1); aa=max(0,a[2]-a[0])*max(0,a[3]-a[1]); ba=max(0,b[2]-b[0])*max(0,b[3]-b[1])
    return inter/(aa+ba-inter) if aa+ba-inter>0 else 0.0


def evaluate_detections(ground_truth: list[dict], predictions: list[dict], class_names: list[str], iou_threshold: float=0.5) -> dict:
    """Inputs: image_id,class_id,bbox(xyxy); predictions also require confidence."""
    classes=range(len(class_names)); matched=set(); tp=Counter(); fp=Counter(); support=Counter(); aps={}
    gt_by={}
    for i,g in enumerate(ground_truth):
        if not 0<=int(g["class_id"])<len(class_names): raise ValueError("ground-truth class_id outside class_names")
        key=(str(g["image_id"]),int(g["class_id"])); gt_by.setdefault(key,[]).append((i,g)); support[key[1]]+=1
    for c in classes:
        ordered=sorted((p for p in predictions if int(p["class_id"])==c),key=lambda p:float(p["confidence"]),reverse=True)
        curve=[]; cumulative_tp=cumulative_fp=0
        for p in ordered:
            candidates=gt_by.get((str(p["image_id"]),c),[])
            best=max(((iou(p["bbox"],g["bbox"]),idx) for idx,g in candidates if idx not in matched),default=(0,None))
            if best[1] is not None and best[0]>=iou_threshold: matched.add(best[1]); cumulative_tp+=1; tp[c]+=1
            else: cumulative_fp+=1; fp[c]+=1
            curve.append((cumulative_tp,cumulative_fp))
        if support[c]:
            recalls=[t/support[c] for t,_ in curve]; precisions=[t/max(1,t+f) for t,f in curve]
            # 101-point interpolated AP.
            aps[class_names[c]]=sum(max((p for r,p in zip(recalls,precisions) if r>=level),default=0) for level in [x/100 for x in range(101)])/101
        else: aps[class_names[c]]=None
    per_class={}
    cm=[[0 for _ in range(len(class_names)+1)] for _ in range(len(class_names)+1)] # last column/row = background
    for c in classes:
        prec=tp[c]/(tp[c]+fp[c]) if tp[c]+fp[c] else 0.0; rec=tp[c]/support[c] if support[c] else 0.0
        per_class[class_names[c]]={"support":support[c],"true_positives":tp[c],"false_positives":fp[c],"precision":prec,"recall":rec,"f1":2*prec*rec/(prec+rec) if prec+rec else 0.0,"ap50":aps[class_names[c]]}
    # Classification confusion matrix follows classwise greedy localization at IoU threshold.
    used=set()
    for p in sorted(predictions,key=lambda p:float(p["confidence"]),reverse=True):
        pc=int(p["class_id"]); candidates=[(iou(p["bbox"],g["bbox"]),idx,g) for idx,g in enumerate(ground_truth) if str(g["image_id"])==str(p["image_id"]) and idx not in used]
        best=max(candidates,default=(0,None,None),key=lambda row:row[0])
        if best[1] is not None and best[0]>=iou_threshold: used.add(best[1]); cm[int(best[2]["class_id"])][pc]+=1
        else: cm[len(class_names)][pc]+=1
    for idx,g in enumerate(ground_truth):
        if idx not in used: cm[int(g["class_id"])][len(class_names)]+=1
    valid_aps=[v for v in aps.values() if v is not None]
    all_tp=sum(tp.values()); all_fp=sum(fp.values()); all_support=sum(support.values())
    overall_precision=all_tp/(all_tp+all_fp) if all_tp+all_fp else 0.0
    overall_recall=all_tp/all_support if all_support else 0.0
    per_dataset={}
    dataset_names=sorted({str(row.get("source_dataset","UNKNOWN")) for row in ground_truth+predictions})
    for dataset in dataset_names:
        dataset_gt=[row for row in ground_truth if str(row.get("source_dataset","UNKNOWN"))==dataset]
        dataset_pred=[row for row in predictions if str(row.get("source_dataset","UNKNOWN"))==dataset]
        per_dataset[dataset]=_evaluate_core(dataset_gt,dataset_pred,class_names,iou_threshold)
    return {"status":"COMPUTED_FROM_SUPPLIED_RECORDS","iou_threshold":iou_threshold,"ground_truth_count":len(ground_truth),"prediction_count":len(predictions),
            "precision":overall_precision,"recall":overall_recall,"f1":2*overall_precision*overall_recall/(overall_precision+overall_recall) if overall_precision+overall_recall else 0.0,
            "mAP@0.5":sum(valid_aps)/len(valid_aps) if valid_aps else None,"per_class":per_class,"class_support":dict(Counter({name:support[c] for c,name in enumerate(class_names)})),
            "confusion_matrix":cm,"confusion_matrix_labels":list(class_names)+["background"],"per_dataset":per_dataset}


def _evaluate_core(ground_truth,predictions,class_names,iou_threshold):
    """Compact per-dataset summary; uses no data beyond the provided records."""
    matched=set(); tp=fp=0; support=len(ground_truth)
    for pred in sorted(predictions,key=lambda p:float(p["confidence"]),reverse=True):
        candidates=[(iou(pred["bbox"],gt["bbox"]),idx,gt) for idx,gt in enumerate(ground_truth) if str(gt["image_id"])==str(pred["image_id"]) and idx not in matched]
        best=max(candidates,default=(0,None,None),key=lambda row:row[0])
        if best[1] is not None and best[0]>=iou_threshold and int(best[2]["class_id"])==int(pred["class_id"]): matched.add(best[1]); tp+=1
        else: fp+=1
    precision=tp/(tp+fp) if tp+fp else 0.0; recall=tp/support if support else 0.0
    return {"ground_truth_count":support,"prediction_count":len(predictions),"precision":precision,"recall":recall,"f1":2*precision*recall/(precision+recall) if precision+recall else 0.0}
