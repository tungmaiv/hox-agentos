# Superpowers Plugin for OpenCode

This repository includes the [Superpowers](https://github.com/obra/superpowers) plugin system for OpenCode.

## What is Superpowers?

Superpowers is a collection of AI skills and a plugin system that enhances OpenCode with:

- **Skills library**: Pre-built skills for common development tasks
- **Automatic context injection**: Adds relevant context to every conversation
- **Tool mapping**: Adapts between different AI coding tool formats

## Available Skills

- **brainstorming** - Structured brainstorming sessions
- **dispatching-parallel-agents** - Run multiple agents simultaneously
- **executing-plans** - Execute development plans step by step
- **finishing-a-development-branch** - Complete and merge branches
- **receiving-code-review** - Process and act on code review feedback
- **requesting-code-review** - Prepare code for review
- **subagent-driven-development** - Delegate tasks to sub-agents
- **systematic-debugging** - Methodical debugging approach
- **test-driven-development** - TDD workflow guidance
- **using-git-worktrees** - Work with multiple branches simultaneously
- **using-superpowers** - Bootstrap skill loaded automatically
- **verification-before-completion** - Verify work before finishing
- **writing-plans** - Create structured development plans
- **writing-skills** - Create new custom skills

## Quick Start

To install or update Superpowers:

```bash
./install-superpowers.sh
```

Or manually:

```bash
# Clone repository
git clone https://github.com/obra/superpowers.git ~/.config/opencode/superpowers

# Create directories
mkdir -p ~/.config/opencode/plugins ~/.config/opencode/skills

# Create symlinks
ln -s ~/.config/opencode/superpowers/.opencode/plugins/superpowers.js ~/.config/opencode/plugins/superpowers.js
ln -s ~/.config/opencode/superpowers/skills ~/.config/opencode/skills/superpowers

# Restart OpenCode
```

## Usage

Once installed, restart OpenCode and you can:

1. **List available skills**:
   ```
   use skill tool to list skills
   ```

2. **Load a specific skill**:
   ```
   use skill tool to load superpowers/brainstorming
   ```

3. **The bootstrap skill** (`using-superpowers`) loads automatically and provides context about available capabilities

## Project Structure

```
~/.config/opencode/
├── plugins/
│   └── superpowers.js -> superpowers/.opencode/plugins/superpowers.js
├── skills/
│   └── superpowers -> superpowers/skills/
└── superpowers/          # Cloned repository
    ├── .opencode/
    │   └── plugins/
    │       └── superpowers.js
    └── skills/
        └── [skill directories]
```

## Updating

To update to the latest version:

```bash
cd ~/.config/opencode/superpowers
git pull
```

Then restart OpenCode.

## Creating Custom Skills

You can create your own skills in:

- **Personal skills**: `~/.config/opencode/skills/my-skill/`
- **Project skills**: `.opencode/skills/my-project-skill/` in your project

Each skill needs a `SKILL.md` file with YAML frontmatter:

```markdown
---
name: my-skill
description: Use when [condition] - [what it does]
---

# My Skill

[Your skill content here]
```

## Documentation

- [Superpowers Repository](https://github.com/obra/superpowers)
- [OpenCode Documentation](https://opencode.ai/docs/)

## Troubleshooting

If the plugin doesn't load:
1. Check symlinks: `ls -l ~/.config/opencode/plugins/` and `ls -l ~/.config/opencode/skills/`
2. Verify files exist in `~/.config/opencode/superpowers/`
3. Restart OpenCode
4. Check OpenCode logs: `opencode run "test" --print-logs --log-level DEBUG`
