import asyncio
import hashlib
import httpx
from analysis import repository


def test_large_implementation_is_included_and_marked_truncated(monkeypatch):
    content = ('def implemented():\n    return True\n' * 1500).encode()
    def reply(request):
        if '/commits/' in request.url.path:
            return httpx.Response(200, json={'sha': 'a'*40})
        if '/git/trees/' in request.url.path:
            return httpx.Response(200,json={'tree':[{'type':'blob','mode':'100644','size':len(content),'path':'main.py'}]})
        return httpx.Response(200,content=content)
    original = httpx.AsyncClient
    monkeypatch.setattr(repository.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(reply), **kw))
    result = asyncio.run(repository.snapshot('https://github.com/example/project'))
    source = result['files']['main.py']
    assert source['truncated']
    assert len(source['text'].encode()) <= 20000
    assert content.decode().startswith(source['text'])
    assert source['sha256'] == hashlib.sha256(content).hexdigest()
    assert result['truncated_files'] == ['main.py']
