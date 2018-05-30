#!/bin/bash

CFG_DIR="$HOME/.config/btc"
BIN_DIR="$HOME/bin"
ICON_DIR="$HOME/.icons"
APP_DIR="$HOME/.local/share/applications"
DIR="$(dirname $0)"

if [ ! -d $BIN_DIR ]
then
mkdir -p $BIN_DIR
fi

if [ ! -d $ICON_DIR ]
then
mkdir -p $ICON_DIR
fi

if [ ! -d $APP_DIR ]
then
mkdir -p $APP_DIR
fi

mkdir $CFG_DIR
cp $DIR/btc.py $BIN_DIR
cp $DIR/icons/* $ICON_DIR
cp $DIR/btc.desktop $APP_DIR

