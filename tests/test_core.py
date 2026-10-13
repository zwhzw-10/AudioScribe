import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import sys
from unittest.mock import patch
from types import SimpleNamespace
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'helper'))
from minutes import draft_minutes, make_docx, timestamp
from server import Jobs, make_handler, local_models, pcm_chunks


class DraftTests(unittest.TestCase):
    def test_candidate_not_asserted_as_decision(self):
        result = draft_minutes([{'start': 62, 'text': '我们没有同意周五发布，负责人还没确定。'}], '周会')
        self.assertIn('[00:01:02]', result)
        self.assertIn('没有同意', result)
        self.assertIn('决定候选（请核对）', result)
        self.assertIn('参会人员：未明确', result)

    def test_excerpts_cover_end_of_long_recording(self):
        segments = [{'start': i * 30, 'text': f'讨论内容{i}'} for i in range(100)]
        result = draft_minutes(segments, '录音')
        self.assertIn('讨论内容99', result)
        self.assertNotIn('讨论内容98\n', result)

    def test_word_is_valid_and_preserves_chinese_and_xml(self):
        result = make_docx('会议 & <测试>', '负责人：李明\n没有批准 <方案>\x00')
        with zipfile.ZipFile(io.BytesIO(result)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn('_rels/.rels', archive.namelist())
            xml = ET.fromstring(archive.read('word/document.xml'))
            text = ''.join(xml.itertext())
            self.assertIn('没有批准 <方案>', text)
            self.assertIn('李明', text)

    def test_timestamp_long_recording(self):
        self.assertEqual(timestamp(7321.9), '02:02:01')

    @patch('server.ollama')
    def test_reject_cloud_models(self, call):
        call.return_value = {'models': [
            {'name': 'local:1', 'details': {'format': 'gguf'}},
            {'name': 'remote:cloud', 'details': {'format': 'gguf'}},
            {'name': 'hidden', 'remote_host': 'example.com', 'details': {'format': 'gguf'}}]}
        self.assertEqual(local_models(), ['local:1'])


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        cls.jobs = Jobs(cls.temp.name)
        cls.token = 'test-' + 'x' * 40
        cls.origin = 'chrome-extension://' + 'a' * 32
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(cls.jobs, cls.token, cls.origin))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp.cleanup()

    def request(self, path, body=None, headers=None):
        return self.opener.open(urllib.request.Request(self.base + path, data=body,
            headers={'X-Local-Token': self.token, **(headers or {})}), timeout=5)

    def test_token_required(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/status', headers={'X-Local-Token': 'wrong'})
        self.assertEqual(error.exception.code, 401)

    def test_other_extension_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/health', headers={'Origin': 'chrome-extension://' + 'b' * 32})
        self.assertEqual(error.exception.code, 403)

    def test_web_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/health', headers={'Origin': 'https://example.com'})
        self.assertEqual(error.exception.code, 403)

    def test_export_uses_edited_text(self):
        body = json.dumps({'title': '编辑后', 'text': '已人工核对金额：100元'}).encode()
        with self.request('/export', body) as response:
            with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                self.assertIn('100元', archive.read('word/document.xml').decode())

    def test_invalid_upload_does_not_reserve_job(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/upload', b'bad', {'X-Audio-Options': json.dumps({'language': 'bad', 'model': 'base'})})
        self.assertFalse(self.jobs.busy)

    def test_clear_does_not_delete_source_or_models(self):
        source = Path(self.temp.name) / 'source.wav'
        source.write_bytes(b'original')
        self.jobs.update(segments=[{'text': 'private', 'start': 0}], minutes='private')
        with self.request('/clear', b'{}'):
            pass
        self.assertEqual(self.jobs.snapshot()['segments'], [])
        self.assertEqual(source.read_bytes(), b'original')

    def test_busy_job_rejected(self):
        self.jobs.reserve()
        try:
            with self.assertRaises(ValueError):
                self.jobs.reserve()
        finally:
            self.jobs.busy = False


class WorkerTests(unittest.TestCase):
    def test_leading_silence_does_not_lock_language_and_offsets_are_global(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            media = Path(folder) / 'upload.media'
            media.write_bytes(b'fixture')
            calls = []
            class Model:
                def transcribe(self, pcm, **settings):
                    calls.append(settings['language'])
                    if len(calls) == 1:
                        return iter([]), SimpleNamespace(language='en')
                    return iter([SimpleNamespace(start=1, end=3, text='今天讨论预算。', no_speech_prob=0)]), SimpleNamespace(language='zh')
            jobs = Jobs(folder)
            jobs.model, jobs.model_name = Model(), 'base'
            with patch('server.pcm_chunks', return_value=iter([([0] * 480000, 0, 60), ([0] * 480000, 30, 60)])):
                jobs.run(media, {'language': 'auto', 'model': 'base', 'title': '会议'})
            self.assertEqual(calls, [None, None])
            self.assertEqual(jobs.snapshot()['language'], 'zh')
            self.assertEqual(jobs.snapshot()['segments'][0]['start'], 31)
            self.assertFalse(media.exists())

    def test_cancel_preserves_partial_transcript_and_deletes_temporary(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            media = Path(folder) / 'upload.media'
            media.write_bytes(b'fixture')
            jobs = Jobs(folder)
            jobs.model, jobs.model_name = object(), 'base'
            jobs.update(segments=[{'start': 2, 'end': 4, 'text': '已识别内容'}])
            jobs.cancel_event.set()
            jobs.run(media, {'language': 'zh', 'model': 'base', 'title': '会议'})
            self.assertEqual(jobs.snapshot()['state'], 'cancelled')
            self.assertIn('已识别内容', jobs.snapshot()['minutes'])
            self.assertFalse(media.exists())

    @patch('server.local_models', return_value=['local:1'])
    @patch('server.ollama')
    def test_optional_ai_uses_all_chunks_and_preserves_previous_on_failure(self, api, models):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            jobs = Jobs(folder)
            api.return_value = {'response': '待办：未明确，见 [00:00:00]'}
            jobs.summarize([{'start': i, 'text': '内容' * 2100} for i in range(3)], '会议', 'local:1')
            self.assertEqual(api.call_count, 3)
            self.assertIn('录音部分 3', jobs.snapshot()['minutes'])
            previous = jobs.snapshot()['minutes']
            api.side_effect = OSError('offline')
            jobs.summarize([{'start': 0, 'text': '内容'}], '会议', 'local:1')
            self.assertEqual(jobs.snapshot()['minutes'], previous)
            self.assertEqual(jobs.snapshot()['state'], 'error')


if __name__ == '__main__':
    unittest.main()
