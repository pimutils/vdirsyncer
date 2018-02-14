make install-rust
echo "export PATH=$HOME/.cargo/bin/:$PATH" >> $BASH_ENV

sudo apt-get install -y cmake

pip install --user virtualenv
~/.local/bin/virtualenv ~/env
echo ". ~/env/bin/activate" >> $BASH_ENV
. $BASH_ENV
pip install docker-compose

make -e install-dev install-test
if python --version | grep -q 'Python 3.6'; then
    make -e install-style
fi
