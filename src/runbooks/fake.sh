#!/bin/bash

sleep $(( $RANDOM % 10 + 1 ))
echo "oh no!" >&2
exit 1
