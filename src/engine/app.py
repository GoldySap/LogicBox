import time
from typing import Callable, Optional

from engine.core.node import Node
from engine.core.scheduler import Clock, Scheduler
from engine.core.signal import events
from engine.core.input import input
from engine.core.plugins import PluginManager
from engine.core.tasks import TaskRunner
from engine.core.config import Config
from engine.core.diagnostics import Diagnostics
from engine.render.pipeline import UniversalRenderPipeline


class Application:
    """Reusable application loop for games and normal desktop applications."""
    def __init__(self, title: str = "Universal Engine", target_fps: float = 60.0,
                 root: Optional[Node] = None,
                 pipeline: Optional[UniversalRenderPipeline] = None):
        if target_fps <= 0:
            raise ValueError("Target FPS must be positive")
        self.title = title
        self.target_fps = target_fps
        self.root = root or Node("root")
        self.pipeline = pipeline
        self.clock = Clock()
        self.scheduler = Scheduler()
        self.input = input
        self.fixed_step = 1.0 / 60.0
        self._fixed_accumulator = 0.0
        self.services = {}
        self.extensions = []
        self.config = Config()
        self.diagnostics = Diagnostics()
        self.tasks = TaskRunner()
        self.plugins = PluginManager(self)
        self.add_service("config", self.config)
        self.add_service("diagnostics", self.diagnostics)
        self.add_service("tasks", self.tasks)
        self.add_service("input", self.input)
        self.running = False
        self._closed = False
        self.on_start: Optional[Callable[[], None]] = None
        self.on_update: Optional[Callable[[float], None]] = None
        self.on_shutdown: Optional[Callable[[], None]] = None

    def add_service(self, name, service):
        if not isinstance(name, str) or not name:
            raise ValueError("Service name must be a non-empty string")
        self.services[name] = service
        return service

    def get_service(self, name, default=None):
        return self.services.get(name, default)

    def register_extension(self, extension):
        required = ("on_load", "on_unload")
        if not all(callable(getattr(extension, method, None)) for method in required):
            raise TypeError("Extensions require on_load(context) and on_unload(context)")
        extension.on_load(self)
        self.extensions.append(extension)
        return extension

    def process_input_event(self, event):
        if isinstance(event, dict):
            self.root._input(event)
        else:
            self.root._input(event)
        events.publish("app:input", event)

    def start(self):
        if self._closed:
            raise RuntimeError("Application is closed")
        self.running = True
        self.root._enter_tree()
        events.publish("app:started", self)
        if self.on_start:
            self.on_start()

    def stop(self):
        if not self.running:
            for extension in reversed(self.extensions):
                extension.on_unload(self)
            self.extensions.clear()
            self.plugins.unload_all()
            self.tasks.cancel_all()
            return
        self.running = False
        events.publish("app:stopping", self)
        if self.on_shutdown:
            self.on_shutdown()
        for extension in reversed(self.extensions):
            extension.on_unload(self)
        self.extensions.clear()
        self.plugins.unload_all()
        self.tasks.cancel_all()
        self.root._exit_tree()
        events.publish("app:stopped", self)

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.running:
            try:
                self.stop()
            finally:
                self.tasks.shutdown(wait=True)
        else:
            for extension in reversed(self.extensions):
                try:
                    extension.on_unload(self)
                except Exception as exc:
                    self.diagnostics.error(
                        "Extension unload failed",
                        source="application",
                        exception=str(exc),
                    )
            self.extensions.clear()
            self.plugins.unload_all()
        self.tasks.shutdown(wait=True)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def run(self):
        self.start()
        frame_time = 1.0 / self.target_fps
        try:
            while self.running:
                frame_start = time.monotonic()
                delta = self.clock.tick()
                self._fixed_accumulator += delta
                self.scheduler.update()
                if self.on_update:
                    self.on_update(delta)
                events.publish("app:update", delta)
                self.root._process(delta)
                self.input.end_frame()
                while self._fixed_accumulator >= self.fixed_step:
                    self.root._fixed_process(self.fixed_step)
                    events.publish("app:fixed_update", self.fixed_step)
                    self._fixed_accumulator -= self.fixed_step
                if self.pipeline:
                    self.pipeline.render_scene(self.root)
                elapsed = time.monotonic() - frame_start
                if elapsed < frame_time:
                    time.sleep(frame_time - elapsed)
        finally:
            if self.running:
                self.stop()
