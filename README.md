# Medusa 🐍

**Note:** This project is a Work in Progress ⚠️

## Instructions

1. Copy the main.py file to somewhere in your path
2. Source `medusa-cd`
3. Create a `.medusa` file and create your aliases in the format `alias=cmd`

### Example `.medusa` file

```
mypy=mypy .
ls=ls -al
```

### Debugging

Set `MEDUSA_DEBUG=1` in the environment to have medusa log to the `/tmp/medusa/debug.log` file
