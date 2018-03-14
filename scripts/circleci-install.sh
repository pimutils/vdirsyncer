echo "export PATH=$HOME/.cargo/bin/:$HOME/.local/bin/:$PATH" >> $BASH_ENV
. $BASH_ENV

make install-rust
sudo apt-get install -y cmake

pip install --user virtualenv
virtualenv ~/env

echo ". ~/env/bin/activate" >> $BASH_ENV
. $BASH_ENV

pip install docker-compose

make -e install-dev install-test
if python --version | grep -q 'Python 3.6'; then
    make -e install-style
fi
