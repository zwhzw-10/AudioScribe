"""Chrome native bridge. Only framed JSON is written to stdout."""
import json,os,secrets,socket,struct,subprocess,sys,threading,time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from platform_paths import data_directory, runtime_python, deno_path

APP=Path(__file__).resolve().parents[1]
HOME=data_directory('AudioScribe', 'AUDIOSCRIBE_HOME')
MAX_MESSAGE=65536

def read_exact(stream,size):
    result=b''
    while len(result)<size:
        part=stream.read(size-len(result))
        if not part: raise EOFError
        result+=part
    return result

def read_message(stream):
    size=struct.unpack('<I',read_exact(stream,4))[0]
    if not 0<size<=MAX_MESSAGE: raise ValueError('Invalid native message length')
    message=json.loads(read_exact(stream,size))
    if not isinstance(message,dict): raise ValueError('Expected an object')
    return message

def write_message(stream,message):
    data=json.dumps(message,ensure_ascii=False).encode('utf8')
    stream.write(struct.pack('<I',len(data))+data);stream.flush()

class Assistant:
    def __init__(self,home=HOME,app=APP):
        self.home,self.app=home,app
        self.child=None;self.log=None;self.endpoint=None;self.lock=threading.Lock();self.error=None
        self.home.mkdir(parents=True,exist_ok=True,mode=0o700)
        cfg=self.home/'helper/config.json';cfg.parent.mkdir(exist_ok=True,mode=0o700)
        try:
            descriptor=os.open(cfg,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor,'w',encoding='utf8') as stream:
                json.dump({'token':secrets.token_urlsafe(32)},stream)
        self.token=json.loads(cfg.read_text(encoding='utf8'))['token']
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def start(self):
        with self.lock:
            if self.child and self.child.poll() is None:return
            if self.log:self.log.close()
            # Allocate per-host port, avoiding old manually started versions.
            with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
            self.endpoint=f'http://127.0.0.1:{port}'
            env=os.environ.copy();env['AUDIOSCRIBE_HOME']=str(self.home)
            env['HF_HUB_DISABLE_SYMLINKS_WARNING']='1'
            env.setdefault('HF_HUB_OFFLINE','0');
            # Standard HTTPS downloads work reliably with macOS network proxies.
            if sys.platform == 'darwin':
                import certifi
                env.setdefault('HF_HUB_DISABLE_XET','1')
                env.setdefault('SSL_CERT_FILE',certifi.where())
            env['HF_HUB_DISABLE_TELEMETRY']='1';env['PYTHONUTF8']='1'
            env['PYTHONNOUSERSITE']='1';env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
            self.log=open(self.home/'assistant.log','wb')
            python=runtime_python(self.app)
            if not python.is_file():
                raise FileNotFoundError('Bundled Python is missing; reinstall the assistant.')
            self.child=subprocess.Popen([str(python),'-I','-u',str(self.app/'helper/server.py'),'--allow-download','--port',str(port)],
                cwd=self.app,env=env,stdin=subprocess.DEVNULL,stdout=self.log,stderr=self.log,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.error=None

    def status(self):
        if not self.child:return {'state':'stopped'}
        if self.child.poll() is not None:return {'state':'error','error':'Assistant failed to start. Use diagnostics or retry; details are in assistant.log.'}
        try:
            request=urllib.request.Request(self.endpoint+'/health',headers={'X-Local-Token':self.token})
            with self.opener.open(request,timeout=1) as response:health=json.load(response)
            if health.get('ok'):return {'state':'ready','endpoint':self.endpoint,'token':self.token,'version':health.get('version')}
        except Exception:pass
        return {'state':'loading','messageKey':'assistantLoading'}

    def stop(self):
        if self.child and self.child.poll() is None:
            self.child.terminate()
            try:self.child.wait(timeout=8)
            except subprocess.TimeoutExpired:self.child.kill();self.child.wait()
        if self.log:self.log.close();self.log=None
        self.child=None

def main():
    # Installer permits only its explicitly registered extension IDs.
    registration=APP/'native-host.json'
    allowed=json.loads(registration.read_text(encoding='utf8'))['allowed_origins']
    origin=sys.argv[1] if len(sys.argv)>1 else ''
    if origin not in allowed:raise SystemExit('Unauthorized extension')
    assistant=Assistant()
    try:
        while True:
            message=read_message(sys.stdin.buffer);request_id=message.get('id')
            try:
                if message.get('type')=='ensure':assistant.start();result=assistant.status()
                elif message.get('type')=='status':result=assistant.status()
                elif message.get('type')=='stop':assistant.stop();result={'state':'stopped'}
                elif message.get('type')=='diagnostics':
                    log=assistant.home/'assistant.log'
                    tail='No assistant log yet.'
                    if log.exists():
                        with log.open('rb') as stream:
                            stream.seek(max(0,log.stat().st_size-8192));tail=stream.read().decode('utf8',errors='replace')
                    result={'state':'diagnostics','log':tail}
                else:result={'state':'error','error':'Unsupported assistant command'}
                write_message(sys.stdout.buffer,{'id':request_id,**result})
            except Exception as exc:write_message(sys.stdout.buffer,{'id':request_id,'state':'error','error':str(exc)})
    except EOFError:pass
    finally:assistant.stop()

if __name__=='__main__':main()
