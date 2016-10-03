#!/bin/sh

# Do not add -x here, otherwise secrets are leaked
set -e

SELF_DIR="$(dirname $0)"
GIT_COMMIT_PATH="$SELF_DIR/../.hypothesis/examples"

if [ -z "$encrypted_a527bcd44658_key" ]; then
    echo "Not executing on third-party PRs"
    exit 0
fi

_is_dirty() {
    (! git diff-index --quiet HEAD $GIT_COMMIT_PATH) || [ "$(git status --porcelain $GIT_COMMIT_PATH | tail -n1)" != "" ]
}

openssl aes-256-cbc -K $encrypted_a527bcd44658_key -iv $encrypted_a527bcd44658_iv -in $SELF_DIR/id_travis.enc -out /tmp/id_travis -d

chmod 600 /tmp/id_travis

eval `ssh-agent -s`
ssh-add /tmp/id_travis

if _is_dirty; then
    git config --global push.default simple
    git config --global user.email "travis@pimutils.org"
    git config --global user.name "Travis CI for pimutils"

    git remote set-url origin git@github.com:pimutils/vdirsyncer
    if [ -n "$TRAVIS_PULL_REQUEST_BRANCH" ]; then
        git checkout "$TRAVIS_PULL_REQUEST_BRANCH"
    else
        git checkout "$TRAVIS_BRANCH"
    fi

    git add -fA $GIT_COMMIT_PATH
    git commit -m "Hypothesis examples, job $TRAVIS_JOB_NUMBER"

    for i in `seq 10`; do
        echo "push: try $i"
        if git push; then break; fi
        git pull --rebase
    done
else
    echo "Nothing to commit"
fi
