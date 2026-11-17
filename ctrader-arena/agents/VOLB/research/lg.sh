#!/bin/bash
# usage: lg.sh ts bid10 ask10 bid20 ask20 bid30 ask30
f=/home/user/treasure/ctrader-arena/agents/VOLB/research/dsi_spreads.csv
echo "$1,2464,$2,$3" >> $f; echo "$1,2469,$4,$5" >> $f; echo "$1,2470,$6,$7" >> $f
