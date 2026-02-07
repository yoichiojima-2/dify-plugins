# lawson dify plugins

## development rules

- Always format Python code with `ruff format` before committing
- Run `ruff check --fix` to auto-fix linting issues

## abstract

i'm participating in a competition where we make a dify agent / chatflow / workflow PoCs that can be promoted to lawson, japanese big convenience store chain. the rule is pretty strict, like we can't use tools with API configurations. so in the default setting, we can't save anything, no web fetching, no data extraction. i coundn't find any interesting PoC on that condition, so i have try to use custom tool, which is ./my-first-plugins. it successfully worked on the environment. so i'd like to start actually making valuable dify tools. can you help to make them? i don't really have what to make exactly in my mind, so be creative. i've already tried the dify's builtin knowledge with operation manuals basic informations about lawson, and historical sales data. it is just a vectorstore as far as i know, so historical data might not fit for knowledge because it requires more precise numeric values. 

here's what i'm thinking;
- からあげ店長
    - helps shifts between stuff.
        - stuff just send "この日出れなくなっちゃった then i will search who is more likely to can work on the shift , and send messages to other stuff"
        - analyse sales data, analysing weather and trend and traffics, advice how much karaage kun should be made or anything..
        - knows everything about lawson operations
    
