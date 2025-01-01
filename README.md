# <img src="icon.png" width="25" height="25" alt="isaac thumbs up"> The binding of Isaac - Mod Sorter 

An experimental way of sorting mods for the game The binding of Isaac: Repentance+ 

> [!WARNING]
> **This is a command line tool for now, a GUI will be worked on when the script achieves feature completion.**

## Why?

If you're anything like and use more than 2 mods that change multiple textures, you are bound to encounter overlap. Most of this is solved by merging or renaming mods to be higher/lower on the load order. But this gets annoying, fast.

## How it works

TboI sorts mods as follows:

* Symbols: !@#$%^&*()
* Numbers: 1234567890
* Uppercase Letters: ABC
* Lowercase Letters: abc

> [!IMPORTANT]
> When sorting by numbers, the game does not see 100 lower than 2, instead it counts 100 to be the same as 1. With this, we reserve the first 3 characters of a mod name to sorting
>
> * 001 MOD_NAME_1
> * 002 MOD_NAME_2
> * 003 MOD_NAME_3

I don't expect people to have more than 999 mods for this game, but if that proves wrong, the limit can be changed.