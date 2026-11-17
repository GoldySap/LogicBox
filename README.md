# Universal Engine

Universal Engine is a small, target-agnostic Python engine for node trees,
signals, transformations, and render-command generation.

It is suitable for both interactive applications and games. The core package
has no third-party dependencies. Pygame and ModernGL backends are optional.

## Requirements

- Python 3.9 or newer
- No dependencies for the core engine

## Installation

```powershell
python -m pip install -e .
```

Optional graphics support:

```powershell
python -m pip install -e ".[pygame]"
python -m pip install -e ".[opengl]"
python -m pip install -e ".[all]"
```

## Command Line

```powershell
logicbox smoke --width 40 --height 10
logicbox inspect scene.json
```

## Quick Start

```python
from engine import Node, TransformComponent
from engine.drivers import TerminalGraphicsDriver
from engine.render import RenderableComponent, UniversalRenderPipeline


class TextRenderable(RenderableComponent):
    def get_primitive_type(self):
        return "terminal_text"

    def get_payload(self):
        return {"text": "Hello"}


root = Node("root")
text = Node("text", root)
text.add_component(TransformComponent(position=(2, 3, 0)))
text.add_component(TextRenderable())

pipeline = UniversalRenderPipeline(TerminalGraphicsDriver(width=20, height=8))
pipeline.render_scene(root)
```

## Serialization

Components can provide custom state:

```python
from engine import Component


class Counter(Component):
    def __init__(self):
        super().__init__()
        self.value = 0

    def to_dict(self):
        return {"value": self.value}

    def load_state(self, data):
        self.value = data.get("value", 0)
```

Pass a component registry to `Node.from_dict` to restore components:

```python
restored = Node.from_dict(data, {"Counter": Counter})
```

## Events

```python
from engine import events

events.subscribe("player:*", lambda channel, *args: None)
events.publish("player:spawn")
```

Node bubbling publishes `node:bubble:<event-name>` and
`node:bubble:<node-path>:<event-name>` before propagating to the parent.

## Scheduling

```python
from engine import Application, Scheduler

app = Application(target_fps=60)
app.scheduler.call_later(2.0, print, "Two seconds elapsed")
app.on_update = lambda delta: app.scheduler.update()
```

Use `Scheduler.call_every` for repeating work and `Scheduler.cancel` for
detaching scheduled work.

## Input, Physics, Audio, and UI

```python
from engine import Input, RigidBody, Collider, CollisionWorld, AudioSystem
from engine import Label, Button

input = Input()
input.map_action("jump", "space")

body = RigidBody(mass=1.0)
collider = Collider(trigger=False)
label = Label("Ready")
button = Button("Start")
```

Use `Node.find_by_component(Collider)` or `CollisionWorld.get_collisions(root)`
for broad-phase AABB overlap checks. The physics component supplies velocity,
forces, gravity, and fixed-timestep integration; it is intentionally
dependency-free and can be replaced or extended by a specialized simulation.

## Plugins and Custom Logic

The engine exposes a service and extension host rather than requiring custom
projects to modify engine source:

```python
from engine import Application, Extension


class DomainExtension(Extension):
    def on_load(self, context):
        context.add_service("domain_api", object())

    def on_unload(self, context):
        pass


app = Application()
app.register_extension(DomainExtension())
app.plugins.register("domain", DomainExtension())
app.config.set("project.name", "My Application")
future = app.tasks.submit(my_custom_function, argument)
```

## Rendering Backends

`UniversalRenderPipeline` builds backend-neutral draw commands.
`TerminalGraphicsDriver` is the dependency-free backend.
`PygameGraphicsDriver` provides a 2D application/window backend.
`OpenGLGraphicsDriver` provides the ModernGL backend contract.

Drivers implement `begin_frame`, `execute_command_buffer`, and `end_frame`.