#!/bin/bash
# Install Superpowers plugin for OpenCode
# https://github.com/obra/superpowers

set -e

echo "Installing Superpowers for OpenCode..."

# 1. Clone or update Superpowers
if [ -d ~/.config/opencode/superpowers ]; then
  echo "Updating existing superpowers..."
  cd ~/.config/opencode/superpowers && git pull
else
  echo "Cloning superpowers repository..."
  git clone https://github.com/obra/superpowers.git ~/.config/opencode/superpowers
fi

# 2. Create directories
echo "Creating plugin directories..."
mkdir -p ~/.config/opencode/plugins ~/.config/opencode/skills

# 3. Remove old symlinks if they exist
echo "Cleaning up old symlinks..."
rm -f ~/.config/opencode/plugins/superpowers.js
rm -rf ~/.config/opencode/skills/superpowers

# 4. Create symlinks
echo "Creating symlinks..."
ln -s ~/.config/opencode/superpowers/.opencode/plugins/superpowers.js ~/.config/opencode/plugins/superpowers.js
ln -s ~/.config/opencode/superpowers/skills ~/.config/opencode/skills/superpowers

# 5. Verify installation
echo ""
echo "Verifying installation..."
echo "Plugin symlink:"
ls -l ~/.config/opencode/plugins/superpowers.js

echo ""
echo "Skills symlink:"
ls -l ~/.config/opencode/skills/superpowers

echo ""
echo "Available skills:"
ls ~/.config/opencode/superpowers/skills/

echo ""
echo "Installation complete! Restart OpenCode to load the plugin."
echo ""
echo "To test:"
echo "  1. Restart OpenCode"
echo "  2. Ask: 'What superpowers do you have?'"
echo "  3. Or use: skill tool to list skills"
