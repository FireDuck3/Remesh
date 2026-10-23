from django.test import RequestFactory
from django.views.defaults import server_error


def test_404_page_is_ukrainian_and_links_home(client, settings):
    settings.DEBUG = False
    for url in ["/nema-takoi-storinky/", "/p/nema-takogo-tovaru/"]:
        response = client.get(url)
        html = response.content.decode()
        assert response.status_code == 404
        assert "Сторінку не знайдено" in html and 'href="/"' in html
        assert "REMESH" in html  # the regular layout (header, footer) around it


def test_500_page_is_standalone_and_gives_the_phone(django_assert_num_queries):
    """It must render when everything else is broken: no database, no context processors, no base layout."""
    with django_assert_num_queries(0):
        response = server_error(RequestFactory().get("/"))
    html = response.content.decode()
    assert response.status_code == 500
    assert "Щось пішло не так. Спробуйте пізніше або зателефонуйте +380 98 593 68 15" in html
    assert 'lang="uk"' in html and "<html" in html and "{%" not in html
