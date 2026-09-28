"""Pin and verify public HF weights for isolated local parsing experiments."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def checksum(path,algorithm='sha256'):
    h=hashlib.new(algorithm)
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('repo');parser.add_argument('output',type=Path)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--revision',default='main')
    parser.add_argument('--patterns',nargs='+',default=['*.json','*.safetensors','*.txt','*.model','*.jinja','README.md','LICENSE*'])
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True);args.evidence.mkdir(parents=True,exist_ok=True)
    os.environ['HF_HOME']=str(args.output.parent/'hf-cache')
    os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN']='1';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    os.environ['HF_HUB_DISABLE_XET']='1'
    from huggingface_hub import HfApi,snapshot_download
    api=HfApi(token=False);info=api.model_info(args.repo,revision=args.revision,files_metadata=True)
    upstream={'repo':args.repo,'revision':info.sha,'files':[{'path':f.rfilename,'size':f.size,'blob_id':f.blob_id,'lfs_sha256':f.lfs.sha256 if f.lfs else None} for f in info.siblings]}
    (args.evidence/'upstream.json').write_text(json.dumps(upstream,indent=2)+'\n')
    snapshot_download(args.repo,revision=info.sha,local_dir=args.output,token=False,max_workers=4,
        allow_patterns=args.patterns,
        ignore_patterns=['assets/*','onnx/*','onnx_files/*'])
    files=[]
    for entry in upstream['files']:
        p=args.output/entry['path']
        if not p.is_file():continue
        sha=checksum(p)
        if entry['lfs_sha256']:assert sha==entry['lfs_sha256']
        elif entry['blob_id']:
            raw=p.read_bytes();assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==entry['blob_id']
        files.append({**entry,'actual_bytes':p.stat().st_size,'sha256':sha,'verified':True})
    result={'repo':args.repo,'revision':info.sha,'files':files,'total_bytes':sum(f['actual_bytes'] for f in files)}
    (args.evidence/'identity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'repo':args.repo,'revision':info.sha,'files':len(files),'bytes':result['total_bytes']}),flush=True)


if __name__=='__main__':main()
