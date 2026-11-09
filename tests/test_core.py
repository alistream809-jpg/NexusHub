import shutil, socket, stat, sys, tempfile, time, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexushost.core import mcping, netutil, whitelist
from nexushost.core.controller import ServerController, ServerError, Status, classify, build_command
from nexushost.core.db import Database
from nexushost.core.javamgr import JavaInstall
from nexushost.core.props import Properties

HERE = Path(__file__).resolve().parent


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class FakeJavaMgr:
    def __init__(self, path): self.path = path
    def find(self, major, need_jdk=False): return JavaInstall(self.path, 21, "21", True)


def wait_for(cond, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        if cond(): return True
        time.sleep(0.1)
    return False


class PropertiesTests(unittest.TestCase):
    def test_roundtrip_preserves_comments_and_unicode(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "server.properties"
            p.write_text("#Minecraft server properties\nmotd=A Minecraft Server\nmax-players=20\n")
            props = Properties(p)
            props.set("motd", "Caf\u00e9 \u00a7aGreen = fun: yes")
            props.set("white-list", True)
            props.save()
            text = p.read_text()
            self.assertIn("#Minecraft server properties", text)
            self.assertIn("\\u00E9", text)
            again = Properties(p)
            self.assertEqual(again.get("motd"), "Caf\u00e9 \u00a7aGreen = fun: yes")
            self.assertTrue(again.get_bool("white-list"))
            self.assertEqual(again.get_int("max-players"), 20)


class DatabaseTests(unittest.TestCase):
    def test_crud_and_settings(self):
        with tempfile.TemporaryDirectory() as d:
            db = Database(Path(d) / "t.db")
            rec = db.add_server(name="A", type="Paper", mc_version="1.21", ram_mb=2048, port=25565, path=str(Path(d) / "a"))
            self.assertEqual(db.get_server(rec.id).name, "A")
            db.update_server(rec.id, ram_mb=4096, auto_stop_enabled=False)
            got = db.get_server(rec.id)
            self.assertEqual(got.ram_mb, 4096); self.assertFalse(got.auto_stop_enabled)
            with self.assertRaises(ValueError): db.update_server(rec.id, evil="x")
            db.set_setting("k", "v"); db.set_setting("k", "w")
            self.assertEqual(db.get_setting("k"), "w")
            db.delete_server(rec.id); self.assertEqual(db.list_servers(), [])


class ClassifyTests(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(classify("[12:00:00 ERROR]: boom"), "error")
        self.assertEqual(classify("\tat net.minecraft.Foo.bar(Foo.java:1)"), "error")
        self.assertEqual(classify("[12:00:00 WARN]: slow"), "warn")
        self.assertEqual(classify("[12:00:00 INFO]: Steve joined the game"), "player")
        self.assertEqual(classify("[12:00:00 INFO]: <Bob> Alice joined the game"), "info")


class WhitelistTests(unittest.TestCase):
    def test_offline_uuid_matches_java(self):
        # Java: UUID.nameUUIDFromBytes("OfflinePlayer:Notch")
        self.assertEqual(whitelist.offline_uuid("Notch"), "b50ad385-829d-3141-a216-7e7d7539ba7f")
    def test_add_remove(self):
        with tempfile.TemporaryDirectory() as d:
            whitelist.add(d, "Steve", online_mode=False)
            self.assertEqual([e["name"] for e in whitelist.read(d)], ["Steve"])
            with self.assertRaises(whitelist.WhitelistError): whitelist.add(d, "steve", online_mode=False)
            with self.assertRaises(whitelist.WhitelistError): whitelist.add(d, "bad name!", online_mode=False)
            whitelist.remove(d, "STEVE"); self.assertEqual(whitelist.read(d), [])


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        wrapper = self.tmp / "fake_java"
        wrapper.write_text(f"#!/bin/sh\nexec {sys.executable} {HERE / 'fake_mc.py'}\n")
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
        self.db = Database(self.tmp / "t.db")
        self.port = free_port()
        folder = self.tmp / "srv"; folder.mkdir()
        (folder / "server.jar").write_bytes(b"x")
        (folder / "server.properties").write_text(f"server-port={self.port}\n")
        rec = self.db.add_server(name="T", type="Vanilla", mc_version="1.21", ram_mb=1024, port=self.port,
                                 path=str(folder), jar_file="server.jar", auto_stop_seconds=3)
        self.c = ServerController(rec, self.db, FakeJavaMgr(str(wrapper)))
        self.states, self.lines = [], []
        self.c.on_status.connect(self.states.append)
        self.c.on_line.connect(lambda k, t: self.lines.append((k, t)))

    def tearDown(self):
        self.c.kill(); wait_for(lambda: not self.c.running, 10)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def start_online(self):
        self.c.start()
        self.assertEqual(self.c.status, Status.STARTING)
        self.assertTrue(wait_for(lambda: self.c.status == Status.ONLINE), "never became ONLINE")

    def test_starting_is_not_online_until_done_line(self):
        self.c.start()
        self.assertEqual(self.c.status, Status.STARTING)   # must NOT claim online yet
        self.assertTrue(wait_for(lambda: self.c.status == Status.ONLINE))
        self.assertEqual(mcping.status("127.0.0.1", self.port)["max"], 20)   # a real listening server

    def test_graceful_stop_saves_then_stops(self):
        self.start_online()
        self.c.stop()
        self.assertTrue(wait_for(lambda: self.c.status == Status.STOPPED))
        texts = [t for _, t in self.lines]
        self.assertTrue(any("Saved the game" in t for t in texts))
        self.assertEqual(self.states[-3:], [Status.ONLINE, Status.STOPPING, Status.STOPPED])
        self.assertTrue(netutil.port_available(self.port))                    # port really released

    def test_players_and_commands(self):
        self.start_online()
        self.c.send_command("fakejoin Steve")
        self.assertTrue(wait_for(lambda: self.c.player_count == 1))
        self.assertEqual(sorted(self.c.player_names), ["Steve"])
        self.assertTrue(wait_for(lambda: self.c._ping_count == 1, 8))         # confirmed by the server itself
        self.c.send_command("fakeleave Steve")
        self.assertTrue(wait_for(lambda: self.c.player_count == 0))

    def test_autostop_after_last_player_leaves(self):
        self.start_online()
        self.c.send_command("fakejoin Alex")
        self.assertTrue(wait_for(lambda: self.c.player_count == 1))
        time.sleep(1.5)
        self.assertIsNone(self.c._deadline)                                   # no countdown with a player online
        self.c.send_command("fakeleave Alex")
        self.assertTrue(wait_for(lambda: self.c._deadline is not None, 5), "countdown did not start")
        self.assertTrue(wait_for(lambda: self.c.status == Status.STOPPED, 15), "auto shutdown did not happen")
        self.assertEqual(self.c.last_stop_reason, "autostop")
        self.assertTrue(any("Saved the game" in t for _, t in self.lines))

    def test_join_cancels_countdown(self):
        self.c.record.auto_stop_seconds = 6
        self.start_online()
        self.c.send_command("fakejoin A"); self.assertTrue(wait_for(lambda: self.c.player_count == 1))
        self.c.send_command("fakeleave A"); self.assertTrue(wait_for(lambda: self.c._deadline is not None, 5))
        time.sleep(2)
        self.c.send_command("fakejoin B")
        self.assertTrue(wait_for(lambda: self.c._deadline is None, 5), "countdown not cancelled")
        time.sleep(6)
        self.assertEqual(self.c.status, Status.ONLINE)                        # survived past the original deadline

    def test_disabled_autostop(self):
        self.c.record.auto_stop_enabled = False
        self.start_online(); time.sleep(5)
        self.assertEqual(self.c.status, Status.ONLINE)

    def test_crash_detected(self):
        self.start_online()
        self.c.send_command("crash")
        self.assertTrue(wait_for(lambda: self.c.status == Status.CRASHED))

    def test_restart(self):
        self.start_online()
        first = self.c._proc.pid
        self.c.restart()
        self.assertTrue(wait_for(lambda: self.c.status == Status.STOPPED or self.c.status == Status.STARTING, 15))
        self.assertTrue(wait_for(lambda: self.c.status == Status.ONLINE and self.c._proc and self.c._proc.pid != first, 20))

    def test_port_in_use_is_refused(self):
        blocker = socket.socket(); blocker.bind(("0.0.0.0", self.port)); blocker.listen(1)
        try:
            with self.assertRaises(ServerError): self.c.start()
            self.assertEqual(self.c.status, Status.STOPPED)
        finally:
            blocker.close()

    def test_commands_refused_when_offline(self):
        with self.assertRaises(ServerError): self.c.send_command("list")

    def test_force_kill_hung_server(self):
        self.start_online()
        self.c.kill()
        self.assertTrue(wait_for(lambda: not self.c.running))

    def test_missing_jar(self):
        (Path(self.c.record.path) / "server.jar").unlink()
        with self.assertRaises(ServerError): self.c.start()


class CommandTests(unittest.TestCase):
    def test_commands(self):
        with tempfile.TemporaryDirectory() as d:
            db = Database(Path(d) / "t.db")
            (Path(d) / "s.jar").write_bytes(b"x")
            rec = db.add_server(name="X", type="Vanilla", mc_version="1", ram_mb=3072, port=1, path=d, jar_file="s.jar", jvm_args="-XX:+UseG1GC")
            cmd = build_command(rec, "java")
            self.assertEqual(cmd[0], "java"); self.assertIn("-Xmx3072M", cmd); self.assertIn("-XX:+UseG1GC", cmd)
            self.assertEqual(cmd[-3:], ["-jar", "s.jar", "nogui"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
