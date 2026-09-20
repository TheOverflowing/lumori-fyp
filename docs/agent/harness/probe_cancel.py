"""Exercise real installed Harness ACP cancellation against a fake local SSE provider."""
import asyncio,hashlib,json,pathlib,threading,sys,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from deepseek_harness_runtime import bundled_runtime_path
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from app.harness_profile import profile_patch
p=pathlib.Path(__file__).resolve().parent
requests=[]; started=threading.Event(); release=threading.Event()
class FakeProvider(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));number=len(requests)+1;requests.append({'path':self.path,'body':body,'attempt':number})
  self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
  chunk={'id':f'offline-cancel-{number}','object':'chat.completion.chunk','created':1,'model':'deepseek-flash','choices':[{'index':0,'delta':{'role':'assistant','content':'partial' if number==1 else f'offline complete {number}'},'finish_reason':None}]}
  try:
   self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode());self.wfile.flush()
   if number==1:started.set();release.wait(10)
   chunk['choices'][0].update({'delta':{},'finish_reason':'stop'});chunk['usage']={'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}
   self.wfile.write(('data: '+json.dumps(chunk)+'\n\ndata: [DONE]\n\n').encode());self.wfile.flush()
  except (BrokenPipeError,ConnectionResetError):pass
async def main():
 http=ThreadingHTTPServer(('127.0.0.1',0),FakeProvider);threading.Thread(target=http.serve_forever,daemon=True).start()
 patch=p/'cancel-profile.patch.yml';sessionroot=p/'cancel-sessions';patch.write_text(json.dumps(profile_patch('deepseek-flash',f'http://127.0.0.1:{http.server_port}/v1',4096,sessionroot),indent=2)+'\n')
 env={'PATH':'/usr/bin:/bin','PKG_NATIVE_CACHE_PATH':str(p/'native-cache'),'DSH_HOME':str(p/'dsh-home'),'FYP_HARNESS_PROXY_TOKEN':'no-real-key-probe'}
 frames=[];results={};stderrs=[];sessionid=None
 async def launch():
  proc=await asyncio.create_subprocess_exec(str(bundled_runtime_path()),'--profile','education','--patch',str(patch),cwd=p,env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
  errtask=asyncio.create_task(proc.stderr.read())
  async def send(method,params,requestid=None):
   frame={'jsonrpc':'2.0','method':method,'params':params}
   if requestid is not None:frame['id']=requestid
   frames.append({'direction':'sent','frame':frame});proc.stdin.write((json.dumps(frame)+'\n').encode());await proc.stdin.drain()
  async def request(i,method,params):
   await send(method,params,i)
   while True:
    line=await asyncio.wait_for(proc.stdout.readline(),20)
    if not line:raise RuntimeError('EOF')
    data=json.loads(line);frames.append({'direction':'received','frame':data})
    if data.get('id')==i:return data
  async def close():
   proc.stdin.close()
   try:await asyncio.wait_for(proc.wait(),5)
   except TimeoutError:proc.kill();await proc.wait()
   stderrs.append((await errtask).decode());return proc.returncode
  return request,send,close
 close=None
 try:
  request,send,close=await launch();results['initialize']=await request(1,'initialize',{'protocolVersion':1,'clientInfo':{'name':'fyp-cancel-probe','version':'1'},'clientCapabilities':{}})
  results['new']=await request(2,'session/new',{'cwd':str(p),'mcpServers':[]});sessionid=results['new']['result']['sessionId']
  pending=asyncio.create_task(request(3,'session/prompt',{'sessionId':sessionid,'prompt':[{'type':'text','text':'First slow offline probe.'}]}))
  assert await asyncio.to_thread(started.wait,5), 'Fake provider never received request'
  try:await asyncio.wait_for(asyncio.shield(pending),0.2);raise AssertionError('slow response unexpectedly completed')
  except TimeoutError:results['controller_timeout']=True
  await send('session/cancel',{'sessionId':sessionid});t=time.monotonic();results['cancelled_prompt']=await asyncio.wait_for(pending,5);results['cancel_settlement_seconds']=time.monotonic()-t;release.set()
  results['new_prompt_same_session']=await request(4,'session/prompt',{'sessionId':sessionid,'prompt':[{'type':'text','text':'Second fast offline probe.'}]})
  results['close_first']=await request(5,'session/close',{'sessionId':sessionid});results['first_exit']=await close();close=None
  request,send,close=await launch();results['initialize_restart']=await request(6,'initialize',{'protocolVersion':1,'clientInfo':{'name':'fyp-cancel-probe','version':'1'},'clientCapabilities':{}})
  results['resume']=await request(7,'session/resume',{'sessionId':sessionid,'cwd':str(p),'mcpServers':[]})
  results['new_prompt_after_restart']=await request(8,'session/prompt',{'sessionId':sessionid,'prompt':[{'type':'text','text':'Third offline probe after restart.'}]})
  results['close_second']=await request(9,'session/close',{'sessionId':sessionid});results['second_exit']=await close();close=None
 except Exception as e:results['error']=repr(e)
 finally:
  release.set()
  if close is not None:results['final_exit']=await close()
  http.shutdown();http.server_close()
  durable=[]
  for f in sorted(sessionroot.rglob('*')):
   if f.is_file():durable.append({'path':str(f),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
  data={'results':results,'frames':frames,'fake_provider_requests':requests,'durable_files':durable,'real_model_calls':0,'stderr':stderrs}
  (p/'cancel-probe.json').write_text(json.dumps(data,indent=2)+'\n')
  print(json.dumps({'results':results,'fake_provider_calls':len(requests),'stderr':stderrs,'durable_files':durable},indent=2))
asyncio.run(main())
