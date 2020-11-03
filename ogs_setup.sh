#!/bin/bash

mkdir /gtp2ogs-node
cd /gtp2ogs-node
npm install gtp2ogs
git clone -b devel https://github.com/online-go/gtp2ogs
cd /gtp2ogs-node/gtp2ogs
git branch
npm install
npm i -g npm
cd /content/Go