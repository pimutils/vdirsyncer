pip install --use-mirrors .
pip install --use-mirrors -r requirements.txt
[[ -z "$DAV_SERVER" ]] && DAV_SERVER=radicale

radicale_deps() {
    if [[ "$RADICALE_STORAGE" == "database" ]]; then
        pip install --use-mirrors sqlalchemy
    fi
}

davserver_radicale() {
    pip install --use-mirrors radicale
}

davserver_radicale_git() {
    pip install git+https://github.com/Kozea/Radicale.git
}

davserver_$DAV_SERVER
