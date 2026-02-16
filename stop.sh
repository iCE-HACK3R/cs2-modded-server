#!/usr/bin/env bash

ps -ef | grep install.sh | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
ps -ef | grep install.log | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
ps -ef | grep gcp.sh | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
ps -ef | grep hlds_run | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
ps -ef | grep hlds_linux | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
ps -ef | grep SCREEN | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
