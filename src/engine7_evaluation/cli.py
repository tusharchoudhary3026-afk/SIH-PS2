from __future__ import annotations
import argparse
from .artifacts import write_artifacts
from .manifest import load_tile_manifest,split_records


def main():
    parser=argparse.ArgumentParser(description="Write observed dataset/split/leakage artifacts; detector metrics are omitted unless supplied to the Python API.")
    parser.add_argument("--manifest",required=True,help="Existing dataset-builder manifest.csv")
    parser.add_argument("--image-root",help="Images root with <split>/<tile>.<ext>")
    parser.add_argument("--label-root",help="Labels root with <split>/<tile>.txt")
    parser.add_argument("--tile-size",type=int,default=640)
    parser.add_argument("--out",required=True)
    parser.add_argument("--assign-splits",action="store_true",help="Assign group-aware splits from actually populated group metadata")
    parser.add_argument("--seed",type=int,default=0)
    args=parser.parse_args()
    records=load_tile_manifest(args.manifest,tile_size=args.tile_size,image_root=args.image_root,label_root=args.label_root)
    info={"group_key":"existing_split","limitation":"Preserved split assignments from supplied manifest."}
    split=records
    if args.assign_splits: split,info=split_records(records,seed=args.seed)
    result=write_artifacts(records,split,args.out,limitations=[info["limitation"],"Engine 4 prediction artifacts and project performance metrics are pending."])
    print(f"Wrote manifest, split manifest, leakage report, and generalization report to {args.out}; project metrics written: {result['metrics_written']}")


if __name__=="__main__": main()
