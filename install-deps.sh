pip install -r requirements.txt
[[ -z "$DAV_SERVER" ]] && DAV_SERVER=radicale
case "$DAV_SERVER" in
    "radicale")
        pip install radicale
        ;;
    "radicale-git")
        pip install git+https://github.com/Kozea/Radicale.git
        ;;
    *)
        echo "$DAV_SERVER is not known."
        exit 1
        ;;
esac
