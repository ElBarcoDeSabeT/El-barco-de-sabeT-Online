# test_core.py

import unittest
from unittest.mock import patch, MagicMock, mock_open
from core import CoreAddon, Channel, Event
import json
import requests


class TestCoreAddon(unittest.TestCase):
    def setUp(self):
        # Setup a temporary directory and cache file path
        self.addon_dir = "/fake/addon/path"
        self.cache_file = "/fake/addon/path/cache.json"
        self.core = CoreAddon(self.addon_dir, self.cache_file)

    @patch('core.requests.get')
    def test_fetch_channels_success(self, mock_get):
        # Mock the JSON response for channels
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"nombre": "Channel1", "tvg_id": "id1", "logo": "logo1.png"},
            {"nombre": "Channel2", "tvg_id": "id2", "logo": "logo2.png"}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        channels = self.core.fetch_channels("http://fakeurl.com/canales.json")
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[0].nombre, "Channel1")
        self.assertEqual(channels[1].tvg_id, "id2")


    @patch('core.requests.get')
    def test_get_tv_programs_success(self, mock_get):
        # Mock the HTML content for TV programs
        mock_html = """
        <li class="content-item">
            <span class="title-section-widget">Monday</span>
            <li class="dailyevent">
                <strong class="dailyhour">20:00</strong>
                <h4 class="dailyteams">Event1</h4>
                <span class="dailychannel">Channel1</span>
                <span class="dailyday">Sport1</span>
            </li>
            <li class="dailyevent">
                <strong class="dailyhour">21:00</strong>
                <h4 class="dailyteams">Event2</h4>
                <span class="dailychannel">Channel2</span>
                <span class="dailyday">Sport2</span>
            </li>
        </li>
        """
        mock_response = MagicMock()
        mock_response.content = mock_html.encode('utf-8')
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        tv_programs = self.core.get_tv_programs("http://fakeurl.com/programacion-tv.html")
        self.assertEqual(len(tv_programs), 2)
        self.assertEqual(tv_programs[0].day, "Monday")
        self.assertEqual(tv_programs[0].event, "Event1")
        self.assertEqual(tv_programs[1].channel, "Channel2")



    def test_find_closest_channel(self):
        channels_names = ["Channel One", "Channel Two", "Channel Three"]
        closest = self.core.find_closest_channel("Chanel One", channels_names)
        self.assertEqual(closest, "Channel One")

        closest = self.core.find_closest_channel("Channel 2", channels_names)
        self.assertEqual(closest, "Channel Two")


    @patch('core.os.path.exists')
    @patch('core.open', new_callable=mock_open, read_data='{"key": "value"}')
    def test_load_cache_success(self, mock_file, mock_exists):
        mock_exists.return_value = True
        cache = self.core.load_cache()
        self.assertIn("key", cache)
        self.assertEqual(cache["key"], "value")

    @patch('core.os.path.exists')
    def test_load_cache_no_file(self, mock_exists):
        mock_exists.return_value = False
        cache = self.core.load_cache()
        self.assertEqual(cache, {})

    @patch('core.open', new_callable=mock_open)
    def test_save_cache_success(self, mock_file):
        data = {"enlaces_canal": ["link1", "link2"], "titulos_canal": ["title1", "title2"]}
        self.core.save_cache(data)
        mock_file.assert_called_with(self.cache_file, "w", encoding="utf-8")
        handle = mock_file()
        handle.write.assert_called()

    @patch('core.open', side_effect=IOError("File write error"))
    def test_save_cache_failure(self, mock_file):
        with self.assertLogs('core', level='ERROR') as log:
            self.core.save_cache({"key": "value"})
            self.assertIn("Failed to save cache to", log.output[0])

    @patch('core.urllib.request.urlopen')
    def test_fetch_proxies_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "proxies": [
                {"proxy": "proxy1:8080", "ip_data": {"continentCode": "AS"}},
                {"proxy": "proxy2:8080", "ip_data": {"continentCode": "EU"}}
            ]
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        proxies = self.core.fetch_proxies("http://fakeurl.com/proxies.json")
        self.assertEqual(len(proxies), 2)
        self.assertEqual(proxies[0]['proxy'], "proxy1:8080")

    @patch('core.urllib.request.urlopen', side_effect=Exception("URL error"))
    def test_fetch_proxies_failure(self, mock_urlopen):
        proxies = self.core.fetch_proxies("http://fakeurl.com/proxies.json")
        self.assertEqual(proxies, [])

    def test_filter_asian_proxies(self):
        proxies = [
            {"proxy": "proxy1:8080", "ip_data": {"continentCode": "AS"}},
            {"proxy": "proxy2:8080", "ip_data": {"continentCode": "EU"}},
            {"proxy": "proxy3:8080", "ip_data": {"continentCode": "AS"}},
        ]
        asian_proxies = self.core.filter_asian_proxies(proxies)
        self.assertEqual(asian_proxies, ["proxy1:8080", "proxy3:8080"])

    @patch('core.requests.get')
    def test_get_web_content_no_proxy_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "Fake HTML content"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        content = self.core.get_web_content("http://fakeurl.com")
        self.assertEqual(content, "Fake HTML content")

    @patch('core.requests.get')
    def test_get_web_content_proxy_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "Fake HTML content via proxy"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        content = self.core.get_web_content("http://fakeurl.com", proxy="proxy1:8080")
        self.assertEqual(content, "Fake HTML content via proxy")

    @patch('core.requests.get', side_effect=requests.RequestException("Network error"))
    def test_get_web_content_failure(self, mock_get):
        content = self.core.get_web_content("http://fakeurl.com")
        self.assertIsNone(content)

    def test_extract_program_links(self):
        html = '''
        <a href="acestream://12345" >Channel1</a>
        <a href="acestream://67890" >Channel2</a>
        '''
        # Prepopulate tv_programs
        self.core.tv_programs = [
            Event(day="Monday", time="20:00", event="Event1", channel="Channel1", sport="Sport1"),
            Event(day="Monday", time="21:00", event="Event2", channel="Channel2", sport="Sport2")
        ]

        enlaces, titulos = self.core.extract_program_links(html)
        self.assertEqual(len(enlaces), 3)
        self.assertEqual(len(titulos), 3)
        self.assertEqual(enlaces, [
            "# Monday", 
            "plugin://script.module.horus?action=play&id=12345",
            "plugin://script.module.horus?action=play&id=67890"
        ])
        self.assertEqual(titulos, [
            "# Monday", 
            'Sport1 20:00 Event1 (Channel1)',
            'Sport2 21:00 Event2 (Channel2)'
        ])

    def test_extract_channel_links(self):
        html = '''
        <a href="acestream://12345" >Channel1</a>
        <a href="acestream://67890" >Channel2</a>
        '''
        enlaces, titulos = self.core.extract_channel_links(html)
        self.assertEqual(len(enlaces), 2)
        self.assertEqual(len(titulos), 2)
        self.assertEqual(enlaces, [
            "plugin://script.module.horus?action=play&id=12345",
            "plugin://script.module.horus?action=play&id=67890"
        ])
        self.assertEqual(titulos, [
            "Channel1 2345",
            "Channel2 7890"
        ])

    @patch('core.open', new_callable=mock_open, read_data='{"enlaces_canal": ["link1"], "titulos_canal": ["title1"]}')
    def test_export_m3u_no_matching_channel(self, mock_file):
        # Prepare mock cache data
        self.core.channels = [Channel(nombre="Channel1", tvg_id="id1", logo="logo1.png")]
        links = ["plugin://script.module.horus?action=play&id=12345"]
        titles = ["Unknown Channel"]
        
        # Mock dialog_interface
        mock_dialog_interface = MagicMock()
        mock_dialog_interface.notification = MagicMock()

        self.core.export_m3u(links, titles, mock_dialog_interface, "/fake/path/test_playlist.m3u")

        # Assert file was opened correctly
        mock_file.assert_called_with("/fake/path/test_playlist.m3u", "w", encoding="utf-8")

        # Assert write calls
        handle = mock_file()
        handle.write.assert_any_call(
            '#EXTM3U url-tvg="https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml, https://raw.githubusercontent.com/Icastresana/lista1/main/epg.xml"\n'
        )
        handle.write.assert_any_call("#EXTINF:-1,Unknown Channel\nplugin://script.module.horus?action=play&id=12345\n")

        # Assert notification was called
        mock_dialog_interface.notification.assert_called_with("Success", "M3U list exported to /fake/path/test_playlist.m3u")

    @patch('core.CoreAddon.fetch_proxies')
    @patch('core.CoreAddon.filter_asian_proxies')
    @patch('core.CoreAddon.get_web_content')
    @patch('core.CoreAddon.extract_program_links')
    @patch('core.CoreAddon.extract_channel_links')
    @patch('core.CoreAddon.save_cache')
    def test_update_list_success(self, mock_save_cache, mock_extract_channel_links, mock_extract_program_links, mock_get_web_content, mock_filter_asian_proxies, mock_fetch_proxies):
        # Mock proxies
        mock_fetch_proxies.return_value = [{"proxy": "proxy1:8080", "ip_data": {"continentCode": "AS"}}]
        mock_filter_asian_proxies.return_value = ["proxy1:8080"]

        # Mock web content fetch
        mock_get_web_content.return_value = "<html></html>"

        # Mock extraction
        mock_extract_program_links.return_value = (["link1"], ["title1"])
        mock_extract_channel_links.return_value = (["link2"], ["title2"])

        # Mock update_list
        with patch('core.time.strftime', return_value="2024-10-15 12:00:00"):
            # Mock dialog_interface
            mock_dialog_interface = MagicMock()

            result = self.core.update_list(mock_dialog_interface)

            # Assertions
            mock_fetch_proxies.assert_called_once_with("https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=json")
            mock_filter_asian_proxies.assert_called_once_with([{"proxy": "proxy1:8080", "ip_data": {"continentCode": "AS"}}])
            mock_get_web_content.assert_any_call("https://elcano.top")
            mock_get_web_content.assert_called_with("https://elcano.top")
            mock_extract_program_links.assert_called_once_with("<html></html>")
            mock_extract_channel_links.assert_called_once_with("<html></html>")
            mock_save_cache.assert_called_once_with({
                "enlaces_eventos": ["link1"],
                "titulos_eventos": ["title1"],
                "enlaces_canal": ["link2"],
                "titulos_canal": ["title2"],
                "origen": "Servidor Principal",
                "fecha": "2024-10-15 12:00:00",
            })
            self.assertEqual(result, {
                "enlaces_eventos": ["link1"],
                "titulos_eventos": ["title1"],
                "enlaces_canal": ["link2"],
                "titulos_canal": ["title2"],
                "origen": "Servidor Principal",
                "fecha": "2024-10-15 12:00:00",
            })

if __name__ == '__main__':
    unittest.main()
