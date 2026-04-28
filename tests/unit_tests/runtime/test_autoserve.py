import json

from gravixlayer.runtime.autoserve import load_google_adk, load_langchain, load_langgraph


def test_loads_google_adk_root_agent(tmp_path):
    project = tmp_path / "adk_sample"
    project.mkdir()
    (project / "agent.py").write_text("root_agent = {'name': 'root'}\n", encoding="utf-8")

    assert load_google_adk(project) == {"name": "root"}


def test_loads_langchain_runnable_without_module_cache_collision(tmp_path):
    adk_project = tmp_path / "adk_sample"
    adk_project.mkdir()
    (adk_project / "agent.py").write_text("root_agent = {'name': 'root'}\n", encoding="utf-8")
    assert load_google_adk(adk_project) == {"name": "root"}

    langchain_project = tmp_path / "langchain_sample"
    langchain_project.mkdir()
    (langchain_project / "agent.py").write_text("agent = {'name': 'chain'}\n", encoding="utf-8")

    assert load_langchain(langchain_project) == {"name": "chain"}


def test_loads_langgraph_target_from_langgraph_json(tmp_path):
    project = tmp_path / "langgraph_sample"
    graph_dir = project / "src" / "agents"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.py").write_text("graph = {'name': 'graph'}\n", encoding="utf-8")
    (project / "langgraph.json").write_text(
        json.dumps({"graphs": {"main": "./src/agents/graph.py:graph"}}),
        encoding="utf-8",
    )

    assert load_langgraph(project) == {"name": "graph"}


def test_loads_langgraph_factory_target_from_langgraph_json(tmp_path):
    project = tmp_path / "deep_agent_sample"
    graph_dir = project / "src" / "deep_agent"
    graph_dir.mkdir(parents=True)
    (graph_dir / "agent.py").write_text(
        "def make_graph():\n    return {'name': 'deep-agent'}\n",
        encoding="utf-8",
    )
    (project / "langgraph.json").write_text(
        json.dumps({"graphs": {"deep_agent": "./src/deep_agent/agent.py:make_graph"}}),
        encoding="utf-8",
    )

    assert load_langgraph(project) == {"name": "deep-agent"}


def test_loads_named_langgraph_target_from_langgraph_json(tmp_path):
    project = tmp_path / "multi_graph_sample"
    graph_dir = project / "src" / "deep_agent"
    graph_dir.mkdir(parents=True)
    (graph_dir / "agent.py").write_text(
        "agent = {'name': 'research'}\n" "def make_graph():\n    return {'name': 'deep-agent'}\n",
        encoding="utf-8",
    )
    (project / "langgraph.json").write_text(
        json.dumps(
            {
                "graphs": {
                    "agent": "./src/deep_agent/agent.py:agent",
                    "deep_agent": "./src/deep_agent/agent.py:make_graph",
                }
            }
        ),
        encoding="utf-8",
    )

    assert load_langgraph(project, "deep_agent") == {"name": "deep-agent"}


def test_langgraph_target_recompiles_module_builder_with_checkpointer(tmp_path):
    project = tmp_path / "hitl_langgraph_sample"
    project.mkdir()
    (project / "graph.py").write_text(
        "class Builder:\n"
        "    def compile(self, checkpointer=None):\n"
        "        return {'checkpointer_injected': checkpointer is not None}\n"
        "builder = Builder()\n"
        "graph = {'checkpointer_injected': False}\n",
        encoding="utf-8",
    )
    (project / "langgraph.json").write_text(
        json.dumps({"graphs": {"travel_planner": "./graph.py:graph"}}),
        encoding="utf-8",
    )

    assert load_langgraph(project, checkpointer=object()) == {"checkpointer_injected": True}


def test_langgraph_target_recompiles_compiled_graph_builder_with_checkpointer(tmp_path):
    project = tmp_path / "compiled_hitl_langgraph_sample"
    project.mkdir()
    (project / "graph.py").write_text(
        "class Builder:\n"
        "    def compile(self, checkpointer=None, **kwargs):\n"
        "        return {\n"
        "            'checkpointer_injected': checkpointer is not None,\n"
        "            'name': kwargs.get('name'),\n"
        "            'interrupt_before': kwargs.get('interrupt_before'),\n"
        "        }\n"
        "class CompiledGraph:\n"
        "    checkpointer = None\n"
        "    builder = Builder()\n"
        "    name = 'simple-agent'\n"
        "    interrupt_before_nodes = ['model']\n"
        "    async def ainvoke(self, input_data, config=None):\n"
        "        return input_data\n"
        "graph = CompiledGraph()\n",
        encoding="utf-8",
    )
    (project / "langgraph.json").write_text(
        json.dumps({"graphs": {"agent": "./graph.py:graph"}}),
        encoding="utf-8",
    )

    assert load_langgraph(project, checkpointer=object()) == {
        "checkpointer_injected": True,
        "name": "simple-agent",
        "interrupt_before": ["model"],
    }


def test_loads_google_adk_package_agent_with_relative_import(tmp_path):
    project = tmp_path / "adk_package_sample"
    package = project / "travel_agent"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "tools.py").write_text("agent_name = 'trip-planner'\n", encoding="utf-8")
    (package / "agent.py").write_text(
        "from .tools import agent_name\nroot_agent = {'name': agent_name}\n",
        encoding="utf-8",
    )

    assert load_google_adk(project) == {"name": "trip-planner"}


def test_loads_langgraph_file_target_with_relative_import(tmp_path):
    project = tmp_path / "langgraph_package_sample"
    graph_dir = project / "src" / "agents"
    graph_dir.mkdir(parents=True)
    (graph_dir / "__init__.py").write_text("", encoding="utf-8")
    (graph_dir / "state.py").write_text("graph_name = 'assistant-graph'\n", encoding="utf-8")
    (graph_dir / "graph.py").write_text(
        "from .state import graph_name\ngraph = {'name': graph_name}\n",
        encoding="utf-8",
    )
    (project / "langgraph.json").write_text(
        json.dumps({"graphs": {"assistant": "./src/agents/graph.py:graph"}}),
        encoding="utf-8",
    )

    assert load_langgraph(project) == {"name": "assistant-graph"}
