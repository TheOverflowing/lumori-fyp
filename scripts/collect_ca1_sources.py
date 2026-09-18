from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import urllib.request,json
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent.parent
SOURCES=[
('du2017','https://aclanthology.org/P17-1123.pdf'),
('gong2022','https://aclanthology.org/2022.coling-1.518.pdf'),
('maity2025','https://arxiv.org/pdf/2501.17397'),
('cheng2025','https://aclanthology.org/2025.acl-long.628.pdf'),
('park2024','https://aclanthology.org/2024.findings-emnlp.477.pdf'),
('lewis2020','https://arxiv.org/pdf/2005.11401'),
('karpukhin2020','https://aclanthology.org/2020.emnlp-main.550.pdf'),
('liu2024','https://aclanthology.org/2024.tacl-1.9.pdf'),
('gao2023','https://aclanthology.org/2023.emnlp-main.398.pdf'),
('es2024','https://aclanthology.org/2024.eacl-demo.16.pdf'),
('saadfalcon2024','https://aclanthology.org/2024.naacl-long.20.pdf'),
('oh2023','https://aclanthology.org/2023.findings-acl.396.pdf'),
('deroy2025','https://raw.githubusercontent.com/mlresearch/v264/main/assets/deroy25a/deroy25a.pdf'),
('mei2025','https://arxiv.org/pdf/2504.08748')]
def fetch(item):
 key,url=item;folder=ROOT/'docs/ca1/literature/papers';folder.mkdir(exist_ok=True)
 path=folder/(key+'.pdf')
 try:
  if not path.exists():
   raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Academic reference review'}),timeout=30).read()
   if not raw.startswith(b'%PDF'):raise ValueError('Not a PDF')
   path.write_bytes(raw)
  reader=PdfReader(path)
  text='\n'.join(f'\n--- PDF page {i+1} ---\n'+(p.extract_text() or '') for i,p in enumerate(reader.pages))
  (ROOT/'tmp/ca1'/(key+'.txt')).write_text(text)
  return {'id':key,'url':url,'pages':len(reader.pages),'status':'downloaded'}
 except Exception as e:return {'id':key,'url':url,'status':'failed','error':str(e)}
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(fetch,SOURCES))
 (ROOT/'docs/ca1/literature/download_manifest.json').write_text(json.dumps(results,indent=2))
 print(json.dumps(results,indent=2))
 if any(x['status']=='failed' for x in results):raise SystemExit(1)
