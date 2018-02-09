#!/bin/bash

# Build the API Docs on the Vagrant machine and copy back the result.

if [[ $USER != "vagrant" ]]; then
    # We are running locally
    echo "Local: Initiating execution of build script on remote vagrant vm."

    # Execute this script on the vm
    vagrant ssh -- -t  /vagrant/doc/build_remote.sh

    # Copy the build results back to us
    scp -r -i ../.vagrant/machines/default/virtualbox/private_key vagrant@192.168.33.10:/vagrant/doc/build/html build_remote

    echo "Done!"
    echo "Generated doc is in folder build_remote."
else
    # We are in the vm
    echo "Remote: Building docs on remote vagrant vm."

    source ~/api-env/bin/activate
    export DJANGO_SETTINGS_MODULE=api.settings.dev_local

    cd /vagrant/doc
    ./build.sh

    echo "Remote: Done building docs, exiting remote shell..."
fi
