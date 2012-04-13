# MWX: a simplified syntax for MWorks

MWX is a syntax and cross-compilation tool for [MWorks](http://github.com/mworks/mworks).  The idea is to provide a lighter-weight syntax for MWorks, more amenable to editing with a text editor.  Along with this convenience also comes increased freedom to build in macro/templating/etc. functionality.

MWX files compile in a fairly direct, line-by-line manner into MWorks XML, and with a proper `mwpp` directive at the top of the file, MWorks can read MWX files directly.

## Basic Syntax

### Object declarations

There are two ways to declare an MWorks object: A "declaration-like" style:

```
trial my_trial[draws='2 cycles']{
	# ...
}
```

and a more "generic" style, that more naturally accomodates objects with names containing spaces (which are allowed by MWorks):

```
trial["My Trial", draws='2 cycles']{
	# ...
}
```
Each of the above examples compiles into the following XML:

```
<trial tag="My Trial" nsamples="1" sampling_method="CYCLE">
	<!-- ... -->
</trial>
```

### Variable declarations

Syntactic sugar is provided to make variable declarations easier to read (though the standard declaration syntax above is also valid)


```
float x = 2.0
local integer y = 2

float reward_volume[groups="Reward, IO"] = 0.02
```

### Actions

Actions may now be written in a way that looks more like a function call, e.g.:

```
wait(100ms)
queue_stimulus(red_square)
update_stimulus_display()
```

compile into:

```
<action type="wait" duration="100ms"></action>
<action type="queue_stimulus" stimulus="red_square"></action>
<action type="update_stimulus_display"></action>
```

In addition, assignment actions may be written more naturally as:

```
x = 2.0
```

which compiles into:

```
<action type="assignment" variable="x" value="2.0"></action>
```

and the `if` action may now be written:

```
if(x < 2){
	wait(100ms)
}
```

which would compile into:

```
<action type="if" condition="x < 2">
	<action type="wait" duration="100ms"></action>
</action>
```

### States and Transitions

States and transitions are specified as follows:

```
state["Init"]{

	wait(100ms)
	x = 2

} transition {
	x > 4 -> yield
	timer_expired -> "Show Stimulus"
}
```

## Installation

MWX may be installed by typing:

	pip install git+https://github.com/davidcox/mwx.git


## Usage

For help, type:

	mwx --help

To convert an existing MWorks XML to MWX:

	mwx --mwx my_protocol.xml > my_protocol.mwx

To convert an MWX file back to XML:

	mwx --xml my_protocol.mwx > my_protocol.xml