import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from engine import (
    AABB,
    Component,
    events,
    Application,
    Matrix4,
    Node,
    Signal,
    TransformComponent,
    Scheduler,
    Clock,
    RigidBody,
    Collider,
    CollisionWorld,
    Input,
    AudioSystem,
    Label,
    Button,
    PluginManager,
    Extension,
    TaskRunner,
    Config,
    Diagnostics,
)
from engine.core.signal import EventBus


class Counter(Component):
    def __init__(self):
        super().__init__()
        self.value = 0

    def to_dict(self):
        return {"value": self.value}

    def load_state(self, data):
        self.value = data.get("value", 0)


class EngineTests(unittest.TestCase):
    def test_child_world_transform_and_dirty_propagation(self):
        root = Node("root")
        root.add_component(TransformComponent(position=(10, 0, 0), scale=(2, 1, 1)))
        child = Node("child", root)
        child.add_component(TransformComponent(position=(3, 0, 0)))
        grandchild = Node("grandchild", child)
        grandchild.add_component(TransformComponent(position=(0, 4, 0)))

        grand_transform = grandchild.get_component(TransformComponent)
        self.assertEqual(grand_transform.get_world_matrix().extract_position(), (16.0, 4.0, 0.0))

        root_transform = root.get_component(TransformComponent)
        root_transform.position = (20, 0, 0)
        self.assertEqual(grand_transform.get_world_matrix().extract_position(), (26.0, 4.0, 0.0))

    def test_reparenting_is_rejected_when_it_would_create_a_cycle(self):
        root = Node("root")
        child = Node("child", root)
        with self.assertRaises(ValueError):
            child.add_child(root)
        with self.assertRaises(ValueError):
            root.add_child(root)

    def test_aabb_transform_includes_rotation_and_scale(self):
        matrix = Matrix4.trs(
            (10, 0, 0),
            (0, 90, 0),
            (2, 3, 4),
        )
        transformed = AABB().transform(matrix)
        self.assertAlmostEqual(transformed.min_bounds[0], 8.0)
        self.assertAlmostEqual(transformed.max_bounds[0], 12.0)
        self.assertAlmostEqual(transformed.min_bounds[2], 0.0)
        self.assertAlmostEqual(transformed.max_bounds[2], 0.0)

    def test_component_serialization_round_trip(self):
        root = Node("root")
        counter = root.add_component(Counter())
        counter.value = 42

        data = root.to_dict()
        restored = Node.from_dict(data, {"Counter": Counter})
        restored_counter = restored.get_component(Counter)

        self.assertIsNotNone(restored_counter)
        self.assertEqual(restored_counter.value, 42)

    def test_signal_once_priority_filter_and_async_listener(self):
        signal = Signal("test")
        received = []

        signal.connect(lambda value: received.append(("filtered", value)), once=True, filter_fn=lambda value: value > 5)
        signal.emit(3)
        signal.emit(7)
        self.assertEqual(received, [("filtered", 7)])

        async def async_listener(value):
            received.append(("async", value))

        signal.connect(async_listener)
        asyncio.run(signal.emit_async(9))
        self.assertIn(("async", 9), received)

    def test_event_bus_wildcard_and_middleware_errors(self):
        bus = EventBus()
        received = []
        bus.subscribe("player:*", lambda *args: received.append(args))
        bus.add_pre_publish_hook(lambda *args: (_ for _ in ()).throw(RuntimeError("hook failure")))
        bus.publish("player:spawn", 7)
        self.assertEqual(received, [(7,)])

    def test_node_bubble_publishes_before_parent(self):
        received = []
        events.clear_all()
        events.subscribe("node:bubble:changed", lambda node, *args: received.append(node.name))

        root = Node("root")
        child = Node("child", root)
        child.emit_bubble("changed")
        self.assertEqual(received, ["child", "root"])
        events.clear_all()

    def test_scheduler_repeats_and_clock_ticks(self):
        scheduler = Scheduler()
        calls = []
        interval_id = scheduler.call_every(0.001, lambda: calls.append("tick"))
        scheduler.update()
        import time
        time.sleep(0.002)
        scheduler.update()
        self.assertGreaterEqual(len(calls), 1)
        self.assertTrue(scheduler.cancel(interval_id))

        clock = Clock(max_delta=0.1)
        time.sleep(0.001)
        self.assertGreater(clock.tick(), 0.0)

    def test_json_save_and_load_round_trip(self):
        root = Node("root")
        root.metadata["enabled"] = True
        child = Node("child", root)
        counter = child.add_component(Counter())
        counter.value = 9

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "scene.json"
            root.save_json(path)
            restored = Node.load_json(path, {"Counter": Counter})

        self.assertEqual(restored.metadata["enabled"], True)
        child_restored = restored.get_node("/root/child")
        self.assertIsNotNone(child_restored)
        self.assertEqual(child_restored.get_component(Counter).value, 9)

    def test_matrix_point_transform_and_camera_matrices(self):
        transform = Matrix4.trs((10, 2, 3), (0, 90, 0), (2, 1, 1))
        point = transform.multiply_point((1, 0, 0))
        self.assertAlmostEqual(point[0], 10.0)
        self.assertAlmostEqual(point[2], 3.0)

        orthographic = Matrix4.orthographic(-1, 1, -1, 1, 0.1, 10)
        self.assertAlmostEqual(orthographic.extract_position()[2], -(10.1 / 9.9))
        perspective = Matrix4.perspective(60, 16 / 9, 0.1, 100)
        self.assertTrue(perspective.m[0] > 0)

    def test_application_lifecycle_and_callbacks(self):
        app = Application(target_fps=120)
        starts = []
        updates = []
        stops = []
        app.on_start = lambda: starts.append(True)
        app.on_update = lambda delta: updates.append(delta)
        app.on_shutdown = lambda: stops.append(True)

        app.start()
        app.stop()
        self.assertTrue(starts)
        self.assertTrue(stops)

    def test_fixed_process_and_input_lifecycle(self):
        class LifecycleComponent(Component):
            def __init__(self):
                super().__init__()
                self.processed = []

            def on_process(self, delta):
                self.processed.append(("process", delta))

            def on_fixed_process(self, fixed_delta):
                self.processed.append(("fixed", fixed_delta))

            def on_input(self, event):
                self.processed.append(("input", event))

        node = Node("node")
        component = node.add_component(LifecycleComponent())
        node._process(0.016)
        node._fixed_process(1 / 60)
        node._input({"action": "jump"})
        self.assertEqual(component.processed[0][0], "process")
        self.assertEqual(component.processed[1][0], "fixed")
        self.assertEqual(component.processed[2][0], "input")

    def test_physics_collision_input_and_ui(self):
        root = Node("root")
        first = Node("first", root)
        first.add_component(TransformComponent(position=(0, 0, 0)))
        first.add_component(Collider(trigger=True))
        first.add_component(RigidBody(mass=2.0, gravity=(0, 0, 0)))

        second = Node("second", root)
        second.add_component(TransformComponent(position=(0.25, 0, 0)))
        second.add_component(Collider())

        collisions = CollisionWorld().get_collisions(root)
        self.assertEqual(len(collisions), 1)

        rigid = first.get_component(RigidBody)
        rigid.add_force(10, 0, 0)
        rigid.on_fixed_process(0.1)
        self.assertGreater(rigid.velocity[0], 0)

        input_system = Input()
        input_system.map_action("jump", "space")
        input_system.set_key("space", True)
        self.assertTrue(input_system.action_pressed("jump"))
        input_system.end_frame()
        self.assertTrue(input_system.action_held("jump"))

        label = Label("Ready")
        self.assertEqual(label.get_payload()["text"], "Ready")
        button = Button("Start")
        button.on_input({"pressed": True})
        self.assertTrue(button.pressed)

    def test_plugin_service_config_task_and_diagnostics(self):
        app = Application(target_fps=120)

        class DomainPlugin(Extension):
            def __init__(self):
                self.loaded = False
                self.unloaded = False

            def on_load(self, context):
                context.add_service("domain", object())
                self.loaded = True

            def on_unload(self, context):
                self.unloaded = True

        plugin = app.plugins.register("domain", DomainPlugin())
        self.assertTrue(plugin.loaded)
        self.assertIsNotNone(app.get_service("domain"))

        app.config.set("project.name", "Custom Application")
        self.assertEqual(app.config.get("project.name"), "Custom Application")
        app.diagnostics.warning("Test diagnostic", source="test", code=100)
        self.assertEqual(app.diagnostics.snapshot("WARNING")[0].source, "test")

        future = app.tasks.submit(lambda x: x * 2, 21)
        self.assertEqual(future.result(timeout=2), 42)
        app.stop()
        app.plugins.unload_all()
        self.assertTrue(plugin.unloaded)

    def test_task_runner_shutdown_is_terminal_and_app_can_stop_once(self):
        app = Application(target_fps=120)
        app.start()
        app.stop()
        app.stop()
        app.close()
        with self.assertRaises(RuntimeError):
            app.tasks.submit(lambda: None)

    def test_matrix_inverse_round_trip_and_invalid_name(self):
        matrix = Matrix4.trs((4, -2, 7), (12, 28, -8), (2, 3, 0.5))
        inverse = matrix.inverse()
        result = matrix.multiply(inverse)
        for index in range(16):
            expected = 1.0 if index in (0, 5, 10, 15) else 0.0
            self.assertAlmostEqual(result.m[index], expected, places=5)
        with self.assertRaises(ValueError):
            Node("/invalid")
        with self.assertRaises(ValueError):
            Matrix4([1.0])

    def test_application_context_manager_and_config_save(self):
        app = Application(target_fps=120)
        with app as context:
            self.assertIs(context, app)
            context.config.set("nested.value", 42)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "config.json"
                context.config.save(path)
                loaded = Config.load(path)
                self.assertEqual(loaded.get("nested.value"), 42)
        with self.assertRaises(RuntimeError):
            app.start()

    def test_large_node_tree_traversal(self):
        root = Node("root")
        for index in range(1000):
            Node(f"node-{index}", root)
        self.assertEqual(len(root.children), 1000)
        self.assertEqual(len(root.find_by_component(TransformComponent)), 0)

    def test_collision_resolution_reverses_relative_velocity(self):
        root = Node("root")
        first = Node("first", root)
        first.add_component(TransformComponent(position=(0, 0, 0)))
        first.add_component(Collider())
        first.add_component(RigidBody(mass=1.0, gravity=(0, 0, 0)))
        second = Node("second", root)
        second.add_component(TransformComponent(position=(0.25, 0, 0)))
        second.add_component(Collider())
        second.add_component(RigidBody(mass=1.0, gravity=(0, 0, 0)))

        first_body = first.get_component(RigidBody)
        second_body = second.get_component(RigidBody)
        first_body.velocity[0] = 1.0
        second_body.velocity[0] = -1.0

        collisions = CollisionWorld().get_collisions(root)
        self.assertEqual(len(collisions), 1)
        collisions[0].resolve(restitution=0.5)
        self.assertLess(first_body.velocity[0], 1.0)
        self.assertGreater(second_body.velocity[0], -1.0)


if __name__ == "__main__":
    unittest.main()
