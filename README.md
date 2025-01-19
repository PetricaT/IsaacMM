# <img src="icon.png" width="25" height="25" alt="isaac thumbs up"> The binding of Isaac - Mod Sorter 

An experimental way of sorting mods for the game The binding of Isaac: Repentance+ 

> [!WARNING]
> **This is a command line tool for now, a GUI will be worked on when the script achieves feature completion.**

## HOW TO USE

> [!CAUTION]
> **BEFORE USING THIS! BACKUP YOUR MODS FOLDER, I AM NOT RESPONSIBLE FOR ANY LOSS OF DATA**

> [!IMPORTANT]
> You need to make sure you have Python installed.

Download this repository by clicking the green button at the top that says `Code` and `Download ZIP`.

``` sh
git clone https://github.com/PetricaT/TboI_Modsort.git
```

Now simply run the script to generate the config file *(the util.py file is the main way of running for now)*

``` sh
python3 util.py
```

This will generate a file called `config.toml`, edit it to point towards your `mods` folder inside the binding of isaac. The path should look something like this: `A:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth\mods`

Now run the script again to generate your current installed mods list

``` sh
python3 util.py
```

This time it will generate a file called `mods.txt`. Move the mods around up or down to set their load order. The higher a mod is in the list, the more priority it will have over other mods. [1 loads last, 9999 loads first].

Once you are done sorting the mods, run the script.... again.

``` sh
python3 util.py
```

This time it will apply the mod order.

If you ever want to reorder your mods, just repeat the last two steps!

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