Notes
=================

Custom commands 
---------------
We can create custom commands to do various ad hoc tasks on the server.

### Adding new commands
To add a new command you must add it as a nested function inside the `register_commands`
function in the `__init__.py` file. 

The command can be added as follows:
```python
@app.cli.command('<my-command-name>')
@click.argument('<arg1>')
def my_custom_command(arg1):
    ...
```
Breakdown of what's happening:
1. `@app.cli.command`: This registers the command to the app. The command name specified here is used
to invoke the command from the CLI.
2. `@click.argument`: This registers any arguments and is optional. 

That's it!

### Running custom commands
Assuming you have a command registered as `my-custom-command`, you can simply invoke it as follows from the CLI:
```bash
superset my-custom-command <arg1_value>
```