# vdirsyncer with Claws Mail

First of all, you must know that you can **not** edit CardDav contacts only **watch** CardDav contacts with Claws-Mail

## Preparation
First of al you need to install vdirsyncer, for that look [here](https://vdirsyncer.pimutils.org/en/stable/installation.html).
Then we need to create some folders:

    mkdir -p ~/.vdirsyncer/status
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

First of all in the general section, we define the status folder path, for some logging information from vdirsyncer. 
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
At the end we create a crontab, so that vdirsyncer syncs automatically every 30 minutes our contacts:

    contrab -e
  
On the end of that file enter this line

    */30 * * * * /usr/local/bin/vdirsyncer sync > /dev/null 2>&1
    
That's all!
