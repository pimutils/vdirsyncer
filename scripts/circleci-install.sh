echo "export PATH=$HOME/.cargo/bin/:$HOME/.local/bin/:$PATH" >> $BASH_ENV
. $BASH_ENV

make install-rust
sudo apt-get install -y cmake

pip install --user virtualenv
virtualenv ~/env

echo ". ~/env/bin/activate" >> $BASH_ENV
. $BASH_ENV
