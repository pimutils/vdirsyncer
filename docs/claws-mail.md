# vdirsyncer with Claws Mail

First of all, Claws-Mail only supports **read-only** functions for vCards.

## Preparation
We need to install vdirsyncer, for that look [here](https://vdirsyncer.pimutils.org/en/stable/installation.html).
Then we need to create some folders:

    mkdir ~/.vdirsyncer
    mkdir ~/.contacts

## Configuration
Now we create the configuration for the vdirsyncer:

    vim ~/.vdirsyncer/config

The config should look like this
```ini
[general]
status_path = "~/.vdirsyncer/status/"

[storage local]
type = "singlefile"
path = "~/.contacts/%s.vcf"

[storage online]
type = "carddav"
url = "CARDDAV_LINK"
username = "USERNAME"
password = "PASSWORD"

[pair contacts]
a = "local"
b = "online"
collections = ["from a", "from b"]
conflict_resolution = "b wins"
```

First of all in the general section, we define the status folder path, for discovered collections and generally stuff that needs to persist between syncs. 
In the local section we define, that all contacts should be sync in a single file, because claws-mail save all contacts in singlefiles,
and the path for the contacts.
In the online section you must change the url, username and password to your setup. In the last section we configurate that in conflict situation, the online contacts win.

## Sync

Now we discover and sync our contacts:

    vdirsyncer discover
    vdirsyncer sync
    
## Claws Mail
Open Claws-Mail.
Got to **Tools** => **Addressbook**.

Click on **Addressbook** => **New vCard**.
Choose a name for the book. 

Then search for the for the vCard in the folder **~/.contacts/**.
Click ok, and you we will see your conatcts.

**Important:** Claws-Mail shows only the contacts with a mail address.

## Crontab
On the end we create a crontab, so that vdirsyncer syncs automatically every 30 minutes our contacts:

    contab -e
  
On the end of that file enter this line

    */30 * * * * /usr/local/bin/vdirsyncer sync > /dev/null
    
That's all!
