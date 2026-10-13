'use strict';
const $ = id => document.getElementById(id);
const HOST = 'com.audioscribe.assistant';
let port, config, connection, serial = 0, pending = new Map();
let file, mediaURL, busy = false, segments = [], rendered = 0, activeTab = 'transcript', pollTimer;
let minutesDirty = false, lastMinutes = '', state = 'idle';
const stamp = (seconds, srt = false) => {
  const ms = Math.max(0, Math.round(seconds * 1000));
  const value = Math.floor(ms / 1000);
  const text = [Math.floor(value / 3600), Math.floor(value / 60) % 60, value % 60].map(n => String(n).padStart(2, '0')).join(':');
  return srt ? `${text},${String(ms % 1000).padStart(3, '0')}` : text;
};
function status(message, detail = '', kind = '') {
  $('status-text').textContent = message;
  $('status-detail').textContent = detail;
  $('status-panel').className = 'status ' + kind;
}
function setBusy(value) {
  busy = value;
  $('start').disabled = value || !file;
  $('cancel').hidden = !value;
  $('progress').hidden = !value;
  $('clear').disabled = value;
  $('summarize').disabled = value || !$('ai-model').value || !segments.length;
  $('refresh-draft').disabled = value;
  $('file').disabled = value;
}
function nativeRequest(type) {
  return new Promise((resolve, reject) => {
    const id = ++serial;
    const timer = setTimeout(() => {pending.delete(id);reject(new Error('助手响应超时，请重新连接。'));}, 12000);
    pending.set(id, {resolve, reject, timer});
    try {port.postMessage({type, id});} catch (error) {clearTimeout(timer);pending.delete(id);reject(error);}
  });
}
async function connect() {
  if (config) return config;
  if (connection) return connection;
  connection = (async () => {
    status('正在连接本地助手…', '请保持此页面打开。', 'busy');
    port = chrome.runtime.connectNative(HOST);
    const currentPort = port;
    currentPort.onMessage.addListener(message => {
      const request = pending.get(message.id);
      if (request) {clearTimeout(request.timer);pending.delete(message.id);request.resolve(message);}
    });
    currentPort.onDisconnect.addListener(() => {
      const message = chrome.runtime.lastError?.message || '助手连接已断开。';
      if (port !== currentPort) return;
      config = null;
      for (const request of pending.values()) {clearTimeout(request.timer);request.reject(new Error(message));}
      pending.clear();
      clearTimeout(pollTimer);
      setBusy(false);
      status('无法连接音频转文字助手', '请运行独立安装包后重新连接。' + message, 'error');
      $('retry').hidden = false;
    });
    let result = await nativeRequest('ensure');
    const started = Date.now();
    while (result.state === 'loading' && Date.now() - started < 120000) {
      await new Promise(resolve => setTimeout(resolve, 700));
      result = await nativeRequest('status');
    }
    if (result.state !== 'ready') throw new Error(result.error || '助手启动超时，请重新连接。');
    config = result;
    $('retry').hidden = true;
    return result;
  })();
  try {return await connection;} finally {connection = null;}
}
async function api(path, options = {}) {
  const cfg = await connect();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), path === '/upload' ? 180000 : 15000);
  try {
    const response = await fetch(cfg.endpoint + path, {...options, headers: {...options.headers, 'X-Local-Token': cfg.token}, signal: controller.signal});
    if (!response.ok) {const data = await response.json();throw new Error(data.error || '操作失败');}
    return response;
  } finally {clearTimeout(timeout);}
}
function error(error) {
  status('操作未完成', error.message || String(error), 'error');
  setBusy(false);
}
function pick(selected) {
  if (busy || !selected) return;
  if (!/\.(mp4|mp3|m4a|wav|webm|ogg|flac)$/i.test(selected.name)) return error(new Error('请选择 MP4、MP3、M4A、WAV 等音频或视频文件。'));
  if (!selected.size || selected.size > 500 * 1024 * 1024) return error(new Error('请选择非空且不超过 500 MB 的文件。'));
  file = selected;
  if (mediaURL) URL.revokeObjectURL(mediaURL);
  mediaURL = URL.createObjectURL(file);
  $('player').src = mediaURL;
  $('file-label').textContent = selected.name;
  $('file-detail').textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB · 已准备好`;
  $('title').value = selected.name.replace(/\.[^.]+$/, '');
  $('start').disabled = false;
  status('录音已准备好', '点击开始转写。第一次使用会下载识别模型。');
}
function selectTab(name) {
  activeTab = name;
  for (const value of ['transcript', 'minutes']) {
    $('tab-' + value).classList.toggle('active', value === name);
    $('tab-' + value).setAttribute('aria-selected', String(value === name));
    $(value + '-panel').hidden = value !== name;
  }
  $('format').querySelector('[value="srt"]').disabled = name === 'minutes';
  if (name === 'minutes' && $('format').value === 'srt') $('format').value = 'docx';
}
function render(data) {
  // Locally edited text wins over server polling.
  for (let i = segments.length; i < data.segments.length; i++) segments.push({...data.segments[i]});
  if (segments.length) $('results').hidden = false;
  for (; rendered < segments.length; rendered++) {
    const index = rendered, segment = segments[index];
    const row = document.createElement('div');row.className = 'segment';
    const button = document.createElement('button');button.className = 'time';button.textContent = stamp(segment.start);
    button.setAttribute('aria-label', '回听 ' + stamp(segment.start));
    button.addEventListener('click', () => {$('player').currentTime = segment.start;$('player').play().catch(() => status('请使用播放器回听', '浏览器无法播放此格式时，请在本机播放器打开原文件。'));});
    const text = document.createElement('textarea');text.value = segment.text;text.rows = 2;text.setAttribute('aria-label', '编辑 ' + stamp(segment.start) + ' 的文字');
    text.addEventListener('input', () => {segments[index].text = text.value;});
    row.append(button, text);$('segments').append(row);
  }
  $('count').textContent = segments.length;
  if (data.minutes && data.minutes !== lastMinutes) {
    if (!minutesDirty) $('minutes').value = data.minutes;
    lastMinutes = data.minutes;
  }
  state = data.state;
  $('progress').value = data.progress || 0;
  const processing = ['loading', 'transcribing', 'summarizing'].includes(state);
  setBusy(processing);
  status(data.message || '已连接', data.error || (processing ? '请保持页面打开。停止可能需要等待当前识别片段结束。' : '可编辑文字、回听核对，并导出保存。'), data.error ? 'error' : processing ? 'busy' : 'done');
}
async function poll() {
  try {
    const data = await (await api('/status')).json();
    render(data);
    if (busy) pollTimer = setTimeout(poll, 1400);
  } catch (err) {error(err);}
}
$('dropzone').addEventListener('click', () => {if (!busy) $('file').click();});
$('dropzone').addEventListener('keydown', event => {if (event.key === 'Enter' || event.key === ' ') {event.preventDefault();if (!busy) $('file').click();}});
$('file').addEventListener('change', () => pick($('file').files[0]));
for (const name of ['dragenter', 'dragover']) $('dropzone').addEventListener(name, event => {event.preventDefault();$('dropzone').classList.add('over');});
for (const name of ['dragleave', 'drop']) $('dropzone').addEventListener(name, event => {event.preventDefault();$('dropzone').classList.remove('over');});
$('dropzone').addEventListener('drop', event => pick(event.dataTransfer.files[0]));
$('start').addEventListener('click', async () => {
  if (!file || busy) return;
  if (segments.length && !confirm('开始新转写会替换当前文字。请先导出需要保留的记录。')) return;
  setBusy(true);clearTimeout(pollTimer);
  try {
    await connect();
    status('正在读取录音…', '只发送到本机助手。', 'busy');
    const options = {language: $('language').value, model: $('model').value, title: $('title').value || file.name};
    await api('/upload', {method: 'POST', body: file, headers: {'Content-Type': 'application/octet-stream', 'X-Audio-Options': JSON.stringify(options).replace(/[\u007f-\uffff]/g, c => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'))}});
    segments = [];rendered = 0;minutesDirty = false;lastMinutes = '';$('segments').replaceChildren();$('minutes').value = '';
    selectTab('transcript');poll();
  } catch (err) {error(err);}
});
$('cancel').addEventListener('click', async () => {try {await api('/cancel', {method: 'POST'});status('正在停止…', '模型下载或当前识别片段结束后停止。', 'busy');}catch(err){error(err);}});
$('retry').addEventListener('click', async () => {try {if(port){port.disconnect();port=null;}config=null;await connect();await poll();} catch(err){error(err);}});
for (const name of ['transcript', 'minutes']) $('tab-' + name).addEventListener('click', () => selectTab(name));
$('minutes').addEventListener('input', () => {minutesDirty = true;});
function extractDraft() {
  const groups = [['讨论摘录', []], ['决定候选（请核对）', []], ['待办候选（请核对）', []]];
  for (const segment of segments) {
    const line = `[${stamp(segment.start)}] ${segment.text}`;groups[0][1].push(line);
    if (/决定|确定|同意|通过|批准|\b(decided|agreed|approved|decision)\b/i.test(segment.text)) groups[1][1].push(line);
    if (/负责|待办|跟进|完成|截止|提交|\b(action|follow.up|deadline|will|assigned)\b/i.test(segment.text)) groups[2][1].push(line);
  }
  if(groups[0][1].length>18){const all=groups[0][1];groups[0][1]=Array.from({length:18},(_,i)=>all[Math.round(i*(all.length-1)/17)]);}
  return [ $('title').value || '会议记录', '', '本地摘录草稿 · 按关键词归类，不是完整语义总结。请回听核对。', '会议日期：未明确', '参会人员：未明确（第一版不自动区分发言人）', '', ...groups.flatMap(([heading,items])=>[heading,...(items.length?items:['未提取到；不代表会议中没有该内容。']),'']), '待确认', '请核对人名、数字、否定语气、负责人和截止日期。'].join('\n');
}
$('refresh-draft').addEventListener('click', () => {if(minutesDirty&&!confirm('重建会替换手动修改的会议草稿。继续吗？'))return;$('minutes').value = extractDraft();minutesDirty = true;});
$('detect-models').addEventListener('click', async () => {
  try {
    const result = await (await api('/models')).json();$('ai-model').replaceChildren();
    for (const model of result.models) {const option=document.createElement('option');option.value=model;option.textContent=model;$('ai-model').append(option);}
    if (!result.models.length) {const option=document.createElement('option');option.value='';option.textContent='未检测到本地模型';$('ai-model').append(option);}
    $('ai-detail').textContent=result.message || '已检测到本地模型。整理速度取决于电脑与模型。';setBusy(busy);
  } catch(err){error(err);}
});
$('ai-model').addEventListener('change', () => setBusy(busy));
$('summarize').addEventListener('click', async () => {
  if(busy||!segments.length||!$('ai-model').value)return;
  if(!confirm('本地 AI 整理将替换当前会议草稿。请先导出需要保留的修改。继续吗？'))return;
  try {await api('/summarize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({segments,title:$('title').value,model:$('ai-model').value})});minutesDirty=false;setBusy(true);poll();}catch(err){error(err);}
});
function download(blob, name) {const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
$('export').addEventListener('click', async () => {
  const title=($('title').value || '会议录音').replace(/[<>:"/\\|?*\x00-\x1f]/g,'_');
  const text=activeTab==='minutes'?$('minutes').value:segments.map(s=>`[${stamp(s.start)}] ${s.text}`).join('\n');
  if(!text.trim())return error(new Error('没有可导出的文字。'));
  const format=$('format').value;
  try {
    if(format==='docx'){const response=await api('/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,text})});download(await response.blob(),title+'.docx');}
    else if(format==='srt'){const srt=segments.map((s,i)=>`${i+1}\n${stamp(s.start,true)} --> ${stamp(s.end,true)}\n${s.text}\n`).join('\n');download(new Blob(['\ufeff'+srt],{type:'text/plain;charset=utf-8'}),title+'.srt');}
    else download(new Blob(['\ufeff'+text],{type:'text/plain;charset=utf-8'}),title+(activeTab==='minutes'?'_会议记录':'_逐字稿')+'.txt');
  }catch(err){error(err);}
});
$('clear').addEventListener('click', async () => {
  if(busy||!confirm('清除本次逐字稿和会议记录？原始录音不会被删除。'))return;
  try {if(config)await api('/clear',{method:'POST'});segments=[];rendered=0;lastMinutes='';minutesDirty=false;$('segments').replaceChildren();$('minutes').value='';$('results').hidden=true;status('本次记录已清除','原始录音未被修改。');}catch(err){error(err);}
});
$('help').addEventListener('click',()=>$('help-dialog').showModal());
$('help-close').addEventListener('click',()=>$('help-dialog').close());
window.addEventListener('beforeunload',event=>{if(busy||segments.length){event.preventDefault();event.returnValue='';}});
