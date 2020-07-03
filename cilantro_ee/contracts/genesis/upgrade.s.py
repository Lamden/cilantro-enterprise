import election_house

# contract for network upgrade Supported features
#
# a) new update available (initiate_update)
# b) vote ready to switch (update_ready_vote)
# c) check for success/failure parameters (check_motion)


# possible votes

upg_lock = Variable() # network upgrade lock only one update can be performed
upg_init_time = Variable()
upg_pepper = Variable()
upg_window = Variable()
branch_name = Variable()
c_branch_name = Variable()

mn_vote = Variable()
dl_vote = Variable()

tot_mn = Variable()
tot_dl = Variable()

# Results
upg_consensus = Variable()

has_voted = Hash(default_value=False)

@construct
def seed():
    upg_lock.set(False)
    upg_consensus.set(False)
    mn_vote.set(0)
    dl_vote.set(0)
    tot_mn.set(0)
    tot_dl.set(0)


@export
def trigger_upgrade(cilantro_branch_name: str, contract_branch_name: str, pepper: str):
    if upg_lock.get() is True:
        assert_parallel_upg_check()

    # for now only master's trigger upgrade
    # test_name.set(election_house.current_value_for_policy('masternodes')[0])
    if ctx.caller in election_house.current_value_for_policy('masternodes') and not has_voted[ctx.caller]:
        upg_lock.set(True)
        #upg_init_time.set(now)
        upg_pepper.set(pepper)
        branch_name.set(cilantro_branch_name)
        c_branch_name.set(contract_branch_name)

        #upg_window.set(datetime.Timedelta(seconds=3000000000))
        mn_vote.set(0)
        dl_vote.set(0)
        #assert election_house.current_value_for_policy('masternodes')

        mnum = len(election_house.current_value_for_policy('masternodes'))
        dnum = len(election_house.current_value_for_policy('delegates'))

        tot_mn.set(mnum)
        tot_dl.set(dnum)

@export
def vote():
    if upg_lock.get() is True:
        if ctx.caller in election_house.current_value_for_policy('masternodes') and not has_voted[ctx.caller]:
            mn_vote.set(mn_vote.get() + 1)
            has_voted[ctx.caller] = True
        if ctx.caller in election_house.current_value_for_policy('delegates') and not has_voted[ctx.caller]:
            dl_vote.set(dl_vote.get() + 1)
            has_voted[ctx.caller] = True

        # if now - upg_init_time.get() >= upg_window.get():
        #     reset_contract()
        
        check_vote_state()
    else:
        assert 'no active upgrade'


def check_vote_state():
    all_nodes = tot_mn.get() + tot_dl.get()
    all_votes = mn_vote.get() + dl_vote.get()

    if all_votes > (all_nodes * 2/3):
        upg_consensus.set(True)

    has_voted.clear()


def reset_contract():
    upg_init_time.set(None)
    upg_consensus.set(False)
    upg_lock.set(False)


def assert_parallel_upg_check():
    assert 'Upgrade under way. Cannot initiate parallel upgrade'
