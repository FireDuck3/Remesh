from django.conf import settings


def test_media_files_are_served(client):
    folder = settings.MEDIA_ROOT / "test-media-serving"
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / "hello.txt"
    file.write_text("hello")
    try:
        r = client.get("/media/test-media-serving/hello.txt")
        assert r.status_code == 200
        assert b"".join(r.streaming_content) == b"hello"
    finally:
        file.unlink()
        folder.rmdir()
