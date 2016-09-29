#!/bin/sh

set -ex

GIT_COMMIT_PATH="$(dirname $0)/../.hypothesis/examples"

if [ "$TRAVIS_PULL_REQUEST" != "false" ]; then
    echo "Not building on pull request."
    exit 0
fi


_is_dirty() {
    (! git diff-index --quiet HEAD $GIT_COMMIT_PATH) || [ "$(git status --porcelain $GIT_COMMIT_PATH | tail -n1)" != "" ]
}

cd "$(dirname $0)"
openssl aes-256-cbc -K $encrypted_a527bcd44658_key -iv $encrypted_a527bcd44658_iv -in id_travis.enc -out /tmp/id_travis -d
chmod 600 /tmp/id_travis

eval `ssh-agent -s`
ssh-add /tmp/id_travis

cd ..

if _is_dirty; then
    git config --global push.default simple
    git config --global user.email "travis@pimutils.org"
    git config --global user.name "Travis CI for pimutils"

    git remote set-url origin git@github.com:pimutils/vdirsyncer
    git checkout $TRAVIS_BRANCH

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
