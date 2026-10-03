from pathlib import Path

from myharness.agents.base import AgentDefinition, SkillDefinition
from myharness.tools.base import BaseTool
from myharness.tools.builtin import CalculatorTool, FileReadTool, BashTool, DateTool, LocationTool
from utils.logger_tool import logger
import yaml
from myharness.tools.registry import ToolRegistry

def load_agent_definition(agent_path: Path) -> AgentDefinition:
    # ============== 检查目录和 agent.yml ==============
    if not agent_path.is_dir():
        logger.error(f"[加载] {agent_path} 不是一个有效的 agent 目录")
        raise FileNotFoundError(f"agent 目录不存在: {agent_path}")

    agent_yml = agent_path / "agent.yml"
    if not agent_yml.is_file():
        logger.error(f"[加载] {agent_yml} 不存在")
        raise FileNotFoundError(f"缺少 agent.yml: {agent_yml}")

    # ===================== 读 yml ========================
    try:
        with open(agent_yml, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"[配置错误] {agent_yml} 不是合法的 YAML")
        raise ValueError(f"agent.yml 格式错误: {e}") from e

    if config is None:
        logger.error(f"[配置错误] {agent_yml} 是空文件")
        raise ValueError(f"agent.yml 是空文件: {agent_yml}")

    if not isinstance(config, dict):
        logger.error(f"[配置错误] {agent_yml} 顶层不是键值对")
        raise ValueError(f"agent.yml 顶层必须是键值对: {agent_yml}")

    logger.info(f"[加载] {agent_path.name}")

    # ================ 读 instructions.md =================
    instructions = ""
    prompt_path = agent_path / "instructions.md"
    if prompt_path.is_file():
        try:
            with open(prompt_path, encoding="utf-8") as f:
                lines = []
                for line in f:
                    if line.strip():
                        lines.append(line.rstrip("\n"))
                instructions = "\n".join(lines)
        except Exception as e:
            logger.error(f"[指令] {prompt_path} 读取失败: {e}")
    else:
        logger.warning(f"[指令] {prompt_path} 不存在，使用空提示词")

    # =================== 扫描 skills/ ====================
    skills: list[SkillDefinition] = []
    skills_dir = agent_path / "skills"
    for name in config.get("skills", []):
        known = {"name", "model", "provider", "temperature", "max_tokens",
                 "enable_thinking", "instructions", "skills", "tools"}
        unknown = set(config.keys()) - known
        if unknown:
            logger.warning(f"[配置] agent.yml 里有无法识别的字段: {unknown}")
        skill_md = skills_dir / name / "SKILL.md"
        if not skill_md.is_file():
            logger.warning(f"[技能] {name} 找不到 ({skill_md})，跳过")
            continue
        skill = load_skill_definition(skill_md)
        if skill is None:
            logger.warning(f"[技能] {skill_md} frontmatter 缺失或格式错误，跳过")
            continue
        if skill.name != name:
            logger.warning(
                f"[技能] 目录名 '{name}' 与 SKILL.md 里的 name '{skill.name}' 不一致，"
                f"以 frontmatter 为准（模型要用 '{skill.name}' 调用）"
            )
        skills.append(skill)
    logger.info(f"[技能] 加载 {len(skills)} 个: {[s.name for s in skills]}")

    # ==================== 组装工具 =====================
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(FileReadTool())
    registry.register(BashTool())
    registry.register(DateTool())
    registry.register(LocationTool())
    registry.load_from_directory(agent_path / "tools")

    tools: list[BaseTool] = []
    for name in config.get("tools", []):
        tool = registry.get_tool(name)
        if tool is None:
            logger.warning(f"[工具] {name} 不存在，已跳过")
            continue
        tools.append(tool)

    logger.info(f"[配置] model={config.get('model')} provider={config.get('provider')}")
    logger.info(f"[工具] {[t.name for t in tools]}")
    logger.debug(f"[技能] {skills}")

    return AgentDefinition(
        name=config.get("name", agent_path.name),
        model=config.get("model", ""),
        provider=config.get("provider", ""),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 4096),
        enable_thinking=config.get("enable_thinking", False),
        instructions=instructions,
        skills=skills,
        tools=tools,
        raw_config=config,
    )

def load_skill_definition(skill_md: Path) -> SkillDefinition | None:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"[技能] {skill_md} 读取失败: {e}")
        return None

    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        logger.warning(f"[技能] {skill_md} 缺少合法的 frontmatter")
        return None

    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        logger.warning(f"[技能] {skill_md} frontmatter 不是合法 YAML: {e}")
        return None

    if not isinstance(meta, dict):
        logger.warning(f"[技能] {skill_md} frontmatter 顶层不是键值对")
        return None

    name = meta.get("name")
    description = meta.get("description")
    if not name or not description:
        logger.warning(f"[技能] {skill_md} 缺少 name 或 description")
        return None

    return SkillDefinition(
        name=name,
        description=description,
        path=skill_md
    )
