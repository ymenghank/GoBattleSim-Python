
'''
The interface module.

This module provides game master file parsing, setting game parameters,
and more convenient battle objects initialization.

'''


import json
import re

from .engine import *




'''
    Useful functions
'''

def quick_raid_battle(attacker, raid_boss,
                      num_attackers=6, num_players=1, friend=0, strategy=STRATEGY_ATTACKER_NO_DODGE, rejoin=False,
                      weather="extreme", num_sims=1000):
    '''
    Simulate a simple raid battle.
    Returns a dict of average outcome.
    '''

    gm = IPokemon._binded_gm

    a_pokemon = IPokemon(attacker)
    d_pokemon = IPokemon(raid_boss)

    a_party = Party()
    a_party.pokemon = [a_pokemon] * num_attackers
    a_party.revive_policy = -1 if rejoin else 0
    d_party = Party(pokemon=[d_pokemon])

    a_player = Player(parties=[a_party])
    a_player.team = 1
    a_player.strategy = strategy
    a_player.clone_multiplier = num_players
    a_player.attack_multiplier = gm.search_friend(friend)
    
    d_player = Player(parties=[d_party], team=0)
    d_player.strategy = STRATEGY_DEFENDER

    battle = Battle(players=[d_player, a_player])
    battle.weather = gm.search_weather(weather)
    battle.time_limit = gm.search_raid_tier(d_pokemon.tier)['timelimit']

    sum_duration = sum_wins = sum_tdo_percent = sum_deaths = 0
    for i in range(num_sims):
        battle.init()
        battle.start()
        battle_outcome = battle.get_outcome(1)
        sum_duration += battle_outcome.duration
        sum_wins += 1 if battle_outcome.win else 0
        sum_tdo_percent += battle_outcome.tdo_percent
        sum_deaths += battle_outcome.num_deaths
    return {
        "Average Duration": sum_duration / num_sims,
        "Win rate": sum_wins / num_sims,
        "Average TDO%": sum_tdo_percent / num_sims,
        "Average #Deaths": sum_deaths / num_sims
    }



def quick_pvp_battle(pokemon_0, pokemon_1, num_shields=[]):
    '''
    Simulate a quick PvP battle.
    Returns the battle score of pokemon_0.
    Note that priority is given to pokemon_0 when simultaneous charged attacks happen.
    '''

    p0 = IPokemon(pokemon_0, pvp=True)
    p1 = IPokemon(pokemon_1, pvp=True)

    if len(num_shields) > 0:
        p0.pvp_strategy = num_shields[0]
    if len(num_shields) > 1:
        p1.pvp_strategy = num_shields[1]

    battle = SimplePvPBattle(p0, p1)
    battle.init()
    battle.start()
    tdo_percent = battle.get_outcome().tdo_percent
    tdo_percent_adjusted = [(p if p < 1 else 1) for p in tdo_percent]

    return tdo_percent_adjusted[0] - tdo_percent_adjusted[1]





'''
    Classes
'''


class GameMaster:
    '''
    This class stores all the releveant the game data.
    It can also pass the data to gobattlesim.Engine.
    '''


    PoketypeList = ["normal", "fighting", "flying", "poison", "ground", "rock", "bug", "ghost",
        "steel", "fire", "water", "grass", "electric", "psychic", "ice", "dragon", "dark", "fairy"]
    InversedPoketypeList = dict([(name, i) for i, name in enumerate(PoketypeList)])

    @staticmethod
    def rm_udrscrs(Str, Category):
        if Category == 'p':
            return ' '.join([s.lower() for s in Str.split('_')][2:])
        elif Category == 'f':
            return ' '.join([s.lower() for s in Str.split('_')[:-1]])
        elif Category == 'c':
            return ' '.join([s.lower() for s in Str.split('_')])
        elif Category == 't':
            return Str.split('_')[-1].lower()



    def __init__(self, file=None):
        '''
        {file} is the filepath to the game master json file.
        '''
        
        self.clear()
        if file is not None:
            self.feed(file)


    def clear(self):
        '''
        Clear all data.
        '''
        
        self.Pokemon = []
        self.PvEMoves = []
        self.PvPMoves = []
        self.CPMultipliers = []
        self.WeatherSettings = []
        self.FriendAttackBonusMultipliers = []
        self.TypeEffectiveness = {}
        self.PvEBattleSettings = {}
        self.PvPBattleSettings = {}


    def feed(self, file):
        '''
        Load and process a game master json file with filepath {file}.
        '''

        with open(file) as gmfile:
            gmdata = json.load(gmfile)

        for template in gmdata["itemTemplates"]:
            tid = template['templateId']

            # Match Pokemon
            if re.fullmatch(r'V\d+_POKEMON_.+', tid):
                pokemon = {}
                pkmInfo = template["pokemonSettings"]
                pokemon['dex'] = int(tid.split('_')[0][1:])
                pokemon['name'] = GameMaster.rm_udrscrs(tid, 'p')
                pokemon['poketype1'] = GameMaster.InversedPoketypeList[GameMaster.rm_udrscrs(pkmInfo['type'], 't')]
                pokemon['poketype2'] = GameMaster.InversedPoketypeList.get(GameMaster.rm_udrscrs(pkmInfo.get('type2',''), 't'), -1)
                pokemon['baseAttack'] = pkmInfo["stats"]["baseAttack"]
                pokemon['baseDefense'] = pkmInfo["stats"]["baseDefense"]
                pokemon['baseStamina'] = pkmInfo["stats"]["baseStamina"]
                pokemon['fastMoves'] = [GameMaster.rm_udrscrs(s,'f') for s in pkmInfo.get('quickMoves', [])]
                pokemon['chargedMoves'] = [GameMaster.rm_udrscrs(s,'c') for s in pkmInfo.get('cinematicMoves', '')]
                evolution = [GameMaster.rm_udrscrs(s,'p') for s in pkmInfo.get('evolutionIds', [])]
                if evolution:
                    pokemon['evolution'] = evolution
                if 'rarity' in pkmInfo:
                    pokemon['rarity'] = pkmInfo['rarity']

                self.Pokemon.append(pokemon)
            
            # Match move, either Fast or Charged
            elif re.fullmatch(r'V\d+_MOVE_.+', tid):
                moveInfo = template['moveSettings']
                move = {}
                move['movetype'] = 'f' if tid.endswith('_FAST') else 'c'
                move['name'] = GameMaster.rm_udrscrs(moveInfo["movementId"], move['movetype'])
                move['poketype'] = GameMaster.InversedPoketypeList[GameMaster.rm_udrscrs(moveInfo["pokemonType"], 't')]
                move['power'] = int(moveInfo.get("power", 0))
                move['duration'] = int(moveInfo["durationMs"])
                move['dws'] = int(moveInfo["damageWindowStartMs"])
                move['energy'] = int(moveInfo.get("energyDelta", 0))
                
                self.PvEMoves.append(move)

            # Match PvP Moves
            elif re.fullmatch(r'COMBAT_V\d+_MOVE_.+', tid):
                moveInfo = template['combatMove']
                move = {}
                move['movetype'] = 'f' if tid.endswith('_FAST') else 'c'
                move['name'] = GameMaster.rm_udrscrs(moveInfo["uniqueId"], move['movetype'])
                move['poketype'] = GameMaster.InversedPoketypeList[GameMaster.rm_udrscrs(moveInfo["type"], 't')]
                move['power'] = int(moveInfo.get("power", 0))
                move['duration'] = int(moveInfo.get('durationTurns', 0))
                move['energy'] = int(moveInfo.get("energyDelta", 0))
                if "buffs" in moveInfo:
                    move['effect'] = MoveEffect(
                        moveInfo["buffs"]["buffActivationChance"],
                        moveInfo["buffs"].get("attackerAttackStatStageChange", 0),
                        moveInfo["buffs"].get("attackerDefenseStatStageChange", 0),
                        moveInfo["buffs"].get("targetAttackStatStageChange", 0),
                        moveInfo["buffs"].get("targetDefenseStatStageChange", 0)
                    )

                self.PvPMoves.append(move)
        
            # Match CPM's
            elif tid == 'PLAYER_LEVEL_SETTINGS':
                for cpm in template["playerLevel"]["cpMultiplier"]:
                    if self.CPMultipliers:
                        # Half level
                        self.CPMultipliers.append(((cpm**2 + self.CPMultipliers[-1]**2)/2)**0.5)
                    self.CPMultipliers.append(cpm)

            # Match Pokemon Types
            elif re.fullmatch(r'POKEMON_TYPE_.+', tid):
                pokemonType = GameMaster.rm_udrscrs(tid, 't')
                self.TypeEffectiveness[pokemonType] = {}
                for idx, mtp in enumerate(template["typeEffective"]["attackScalar"]):
                    self.TypeEffectiveness[pokemonType][GameMaster.PoketypeList[idx]] = mtp

            # Match PvE Battle settings
            elif tid == 'BATTLE_SETTINGS':
                self.PvEBattleSettings = template["battleSettings"]

            # Match PvP Battle settings
            elif tid == 'COMBAT_SETTINGS':
                for name, value in template["combatSettings"].items():
                    self.PvPBattleSettings[name] = value

            # Match PvP Battle settings for buff stats
            elif tid == 'COMBAT_STAT_STAGE_SETTINGS':
                for name, value in template["combatStatStageSettings"].items():
                    self.PvPBattleSettings[name] = value

            # Match weather settings
            elif re.fullmatch(r'WEATHER_AFFINITY_.+', tid):
                weatherName = template["weatherAffinities"]["weatherCondition"]
                if weatherName == 'OVERCAST':
                    weatherName = 'CLOUDY'
                self.WeatherSettings.append({
                    'name': weatherName,
                    'boostedTypes': [GameMaster.rm_udrscrs(s,'t') for s in template["weatherAffinities"]["pokemonType"]]
                })
            elif tid == 'WEATHER_BONUS_SETTINGS':
                self.PvEBattleSettings['weatherAttackBonusMultiplier'] = template["weatherBonusSettings"]["attackBonusMultiplier"]

            # Match friend settings
            elif re.fullmatch(r'FRIENDSHIP_LEVEL_\d+', tid):
                multiplier = template["friendshipMilestoneSettings"]["attackBonusPercentage"]
                self.FriendAttackBonusMultipliers.append({"name": tid, "multiplier": multiplier})

        self.FriendAttackBonusMultipliers.sort(key=lambda x: x["multiplier"])


    def apply(self):
        '''
        Pass the data to simulator engine and apply.
        '''

        # Single-valued battle parameters
        for name, value in self.PvEBattleSettings.items():
            if name == 'sameTypeAttackBonusMultiplier':
                set_parameter("same_type_attack_bonus_multiplier", value)
            elif name == 'maximumEnergy':
                set_parameter("max_energy", value)
            elif name == 'energyDeltaPerHealthLost':
                set_parameter("energy_delta_per_health_lost", value)
            elif name == 'dodgeDurationMs':
                set_parameter("dodge_duration", value)
            elif name == 'swapDurationMs':
                set_parameter("swap_duration", value)
            elif name == 'dodgeDamageReductionPercent':
                set_parameter("dodge_damage_reduction_percent", value)
            elif name == 'weatherAttackBonusMultiplier':
                set_parameter("weather_attack_bonus_multiplier", value)
        # PvP specific parameters
        # Todo: some could conflict with PvE paramters, like STAB.
        for name, value in self.PvPBattleSettings.items():
            if name == "fastAttackBonusMultiplier":
                set_parameter("pvp_fast_attack_bonus_multiplier", value)
            elif name == "chargeAttackBonusMultiplier":
                set_parameter("pvp_charged_attack_bonus_multiplier", value)
        set_stage_multipliers(self.PvPBattleSettings["attackBuffMultiplier"],
                              self.PvPBattleSettings.get("minimumStatStage", None))
        
        # Type effectiveness
        set_num_types(len(GameMaster.PoketypeList))
        for t1, t1_name in enumerate(GameMaster.PoketypeList):
            for t2, t2_name in enumerate(GameMaster.PoketypeList):
                set_effectiveness(t1, t2, self.TypeEffectiveness[t1_name][t2_name])

        # Set weather
        for i, weather in enumerate(self.WeatherSettings):
            for t_name in weather['boostedTypes']:
                set_type_boosted_weather(GameMaster.InversedPoketypeList[t_name], i)


        # Bind this instance to interface classes
        IPokemon.bind_game_master(self)
        IMove.bind_game_master(self)
        
                

    @staticmethod
    def _search(_universe, criteria, _all):
        if isinstance(criteria, str):
            cbfn = lambda x: x['name'].strip().lower() == criteria.strip().lower()
        else:
            cbfn = criteria
        results = []
        for entity in _universe:
            if cbfn(entity):
                if _all:
                    results.append(entity)
                else:
                    return entity
        if _all:
            return results
        else:
            raise Exception("Entity '{}' not found".format(criteria))

        
    def search_pokemon(self, criteria, _all=False):
        '''
        Fetch and return the Pokemon satisfying the criteria.
        
        {criteria} can be string or a callback
        In the first case, it will match each entity's name, case-insensitive
        If {_all} is False, it will return the first match. Otherwise, all matches
        '''
        return GameMaster._search(self.Pokemon, criteria, _all)


    def search_move_pve(self, criteria, _all=False):
        '''
        Fetch and return the PvE Move satisfying the criteria.
        
        {criteria} can be string or a callback
        In the first case, it will match each entity's name, case-insensitive
        If {_all} is False, it will return the first match. Otherwise, all matches
        '''
        return GameMaster._search(self.PvEMoves, criteria, _all)


    def search_move_pvp(self, criteria, _all=False):
        '''
        Fetch and return the PvP Move satisfying the criteria.
        
        {criteria} can be string or a callback
        In the first case, it will match each entity's name, case-insensitive
        If {_all} is False, it will return the first match. Otherwise, all matches
        '''
        return GameMaster._search(self.PvPMoves, criteria, _all)


    def search_cpm(self, level):
        '''
        Fetch and return the CPM corresponding to {level}.
        
        '''
        idx = round(2 * float(level) - 2)
        return self.CPMultipliers[idx]


    def search_weather(self, weather_name):
        '''
        Return the index of the weather by the name {weather_name}. -1 if not found.
        Case-insensitive search.
        
        '''
        for i, weather in enumerate(self.WeatherSettings):
            if weather['name'].lower() == weather_name.lower():
                return i
        return -1
    

    def search_friend(self, friendship):
        '''
        Return the friend attack bonus multiplier of friendship {friendship}.
        Example: "FRIENDSHIP_LEVEL_1", or 1, or "1", "Great", or "great"
        '''

        friendship = str(friendship).strip().lower()
        alter_names = ["none", "good", "great", "ultra", "best"]
        for i, friend_setting in enumerate(self.FriendAttackBonusMultipliers):
            if friendship == str(i):
                return friend_setting["multiplier"]
            elif friendship == alter_names[i]:
                return friend_setting["multiplier"]
        raise Exception("Friend '{}' not found".format(friendship))


    def search_raid_tier(self, tier):
        '''
        Return {boss cpm, boss max_hp, time limit} of tier {tier}.
        {tier} is string, such as "3" (tier 3).
        Note: for now, these data are hardcoded because they are not in the game master file.
        '''
        RaidTierSettings = [
            {"name": "1", "cpm": 0.6, "maxHP": 600, "timelimit": 180000},
            {"name": "2", "cpm": 0.67, "maxHP": 1800, "timelimit": 180000},
            {"name": "3", "cpm": 0.7300000190734863, "maxHP": 3600, "timelimit": 180000},
            {"name": "4", "cpm": 0.7900000214576721, "maxHP": 9000, "timelimit": 180000},
            {"name": "5", "cpm": 0.7900000214576721, "maxHP": 15000, "timelimit": 300000},
            {"name": "6", "cpm": 0.7900000214576721,"maxHP": 18750, "timelimit": 3000000}
        ]

        tier = str(tier)
        for rt in RaidTierSettings:
            if rt["name"] == tier:
                return rt
        raise Exception("Tier {} not found".format(tier))




ROLE_PVE_ATTACKER = "ae"
ROLE_PVP_ATTACKER = "ap"
ROLE_GYM_DEFENDER = "gd"
ROLE_RAID_BOSS = "rb"


class IPokemon(PvPPokemon):
    '''
    Interface Pokemon class.
    Convinient for contructing gobattlesim.engine.Pokemon(/PvPPokemon) objects.
    '''


    _binded_gm = GameMaster()
    
    @classmethod
    def bind_game_master(cls, game_master):
        cls._binded_gm = game_master


    @staticmethod
    def calc_cp(bAtk, bDef, bStm, cpm, atkiv, defiv, stmiv):
        Atk = (bAtk + atkiv) * cpm
        Def = (bDef + defiv) * cpm
        Stm = (bStm + stmiv) * cpm
        return max(10, int( Atk * (Def * Stm)**0.5 / 10 ))


    @staticmethod
    def infer_level_and_IVs(bAtk, bDef, bStm, target_cp):
        CPMultipliers = IPokemon._binded_gm.CPMultipliers
        closest = None
        closest_cp = 0
        min_cpm_i = 0
        max_cpm_i = len(CPMultipliers) - 1
        while min_cpm_i <= max_cpm_i:
            if IPokemon.calc_cp(bAtk, bDef, bStm, CPMultipliers[min_cpm_i], 15, 15, 15) > target_cp:
                break
            min_cpm_i += 1
        while max_cpm_i > 0:
            if IPokemon.calc_cp(bAtk, bDef, bStm, CPMultipliers[max_cpm_i], 0, 0, 0) < target_cp:
                break
            max_cpm_i -= 1
        
        for cpm in CPMultipliers[min_cpm_i : max_cpm_i + 1]:
            for atkiv in range(16):
                for defiv in range(16):
                    for stmiv in range(16):
                        cp = IPokemon.calc_cp(bAtk, bDef, bStm, cpm, atkiv, defiv, stmiv)
                        if cp == target_cp:
                            return (cpm, atkiv, defiv, stmiv)
                        elif closest_cp < cp and cp < target_cp:
                            closest_cp = cp
                            closest = (cpm, atkiv, defiv, stmiv)
        return closest

    

    def __init__(self, *args, **kwargs):
        '''
        If there is a positional argument, it must be an Pokemon/IPokemon instance, or an address to one.

        **kwargs can include:
            name, fmove, cmove, cmoves, level, atkiv, defiv, stmiv, cp, role, tier, immortal, strategy
            
        Some examples:
            Define an attacker:
                (name, fmove, cmove/cmoves, level, atkiv, defiv, stmiv)
            Define an attacker by cp (infer the stats):
                (name, fmove, cmove/cmoves, cp)
            Define a raid boss:
                (name, fmove, cmove, role=ROLE_RAID_BOSS, tier=4)
            Define a gym defender by cp (infer the stats, too):
                (name, fmove, cmove, cp, role=ROLE_GYM_DEFENDER)
        '''

        self.__dict__['tier'] = None
        p_dict = kwargs

        if len(args):
            if isinstance(args[0], Pokemon) or isinstance(args[0], int):
                super.__init__(args[0])
                self.__dict__['tier'] = args[0].__dict__.get('tier', None)
                return
            elif isinstance(args[0], dict):
                p_dict = args[0]
            else:
                raise TypeError("Wrong argument type")
        
        # These are the stats must be worked out
        targets = {"poketype1": 0, "poketype2": 0, "attack": 0, "defense": 0, "max_hp": 0}
        
        sdata = IPokemon._binded_gm.search_pokemon(p_dict['name'])
        bAtk, bDef, bStm = sdata['baseAttack'], sdata['baseDefense'], sdata['baseStamina']
        targets["poketype1"] = sdata["poketype1"]
        targets["poketype2"] = sdata["poketype2"]
        
        role = p_dict.get("role", ROLE_PVE_ATTACKER)
        if role == ROLE_RAID_BOSS or "tier" in p_dict:
            tier = str(p_dict["tier"])
            tier_setting = IPokemon._binded_gm.search_raid_tier(tier)
            targets["attack"] = (sdata['baseAttack'] + 15) * tier_setting['cpm']
            targets["defense"] = (sdata['baseDefense'] + 15) * tier_setting['cpm']
            targets["max_hp"] = tier_setting['maxHP']
            self.__dict__['tier'] = tier
        else:
            if "cp" in p_dict:
                cpm, atkiv, defiv, stmiv = IPokemon.infer_level_and_IVs(bAtk, bDef, bStm, p_dict["cp"])
            else:
                cpm = IPokemon._binded_gm.search_cpm(p_dict.get("level", 40))
                atkiv = p_dict.get("atkiv", 15)
                defiv = p_dict.get("defiv", 15)
                stmiv = p_dict.get("stmiv", 15)
            targets["attack"] = (bAtk + atkiv) * cpm
            targets["defense"] = (bDef + defiv) * cpm
            targets["max_hp"] = int((bStm + stmiv) * cpm)
            if role == ROLE_GYM_DEFENDER:
                targets["max_hp"] *= 2
        super().__init__(**targets)

        # Set up moves
        pvp = (role == ROLE_PVP_ATTACKER) or p_dict.get("pvp", False) or kwargs.get("pvp", False)
        if "fmove" in p_dict:
            self.fmove = IMove(p_dict["fmove"], pvp=pvp)

        raw_cmoves = []
        if "cmove" in p_dict:
            raw_cmoves = [p_dict["cmove"]]
        elif "cmoves" in p_dict:
            raw_cmoves = p_dict["cmoves"]
        self.cmoves = [IMove(cmove, pvp=pvp) for cmove in raw_cmoves]

        # Set up other attributes
        self.immortal = p_dict.get("immortal", False)

        if "pvp_strategy" in p_dict:
            self.pvp_strategy = p_dict["pvp_strategy"]



class IMove(Move):
    '''
    Interface Move class.
    Convinient for contructing gobattlesim.engine.Move objects.
    '''

    _binded_gm = GameMaster()
    
    @classmethod
    def bind_game_master(cls, game_master):
        cls._binded_gm = game_master


    def __init__(self, *args, **kwargs):
        if kwargs.get("pvp", False):
            search_method = IMove._binded_gm.search_move_pvp
        else:
            search_method = IMove._binded_gm.search_move_pve
        move_dict = kwargs
        if len(args) > 0:
            arg = args[0]
            if isinstance(args[0], str):
                move_dict = search_method(args[0])
            elif isinstance(args[0], dict):
                move_dict = args[0]
            elif isinstance(args[0], Move) or isinstance(args[0], int):
                super().__init__(args[0])
                return
            else:
                raise TypeError("Wrong argument type")
        elif "name" in kwargs:
            move_dict = search_method(kwargs["name"])
        move_dict_clean = {}
        for k, v in move_dict.items():
            if isinstance(v, int) or isinstance(v, MoveEffect):
                move_dict_clean[k] = v
        super().__init__(**move_dict_clean)
        



