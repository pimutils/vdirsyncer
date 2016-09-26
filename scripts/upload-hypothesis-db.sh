#!/bin/sh

set -e

eval `ssh-agent -s`
echo -e "$REPO_DEPLOY_KEY" | head -1
echo -e "$REPO_DEPLOY_KEY" | SSH_ASKPASS="false" ssh-add -
cd "$(dirname $0)/.."

git add -A .hypothesis
git commit "Hypothesis examples"
git pull --rebase
git push
