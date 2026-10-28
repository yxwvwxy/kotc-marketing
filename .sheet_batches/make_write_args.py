
import json, sys
ROW = ["", 0, 0, 0, 0, 0, 0, "2026-08-09T23:44:14+00:00"]
start, n = int(sys.argv[1]), int(sys.argv[2])
args = {
  "spreadsheetId": "1-H_EV3dqF62blGc4p2F7CwQvInbGbgQT7TvsFmkgnhs",
  "sheet": "Sheet1",
  "cells": f"O{start}",
  "parseInput": False,
  "values": [ROW]*n,
}
json.dump(args, sys.stdout, separators=(",", ":"))
