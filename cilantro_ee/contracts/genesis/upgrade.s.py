import election_house

# contract for network upgrade Supported features
#
# a) new update available (initiate_update)
# b) vote ready to switch (update_ready_vote)
# c) check for success/failure parameters (check_motion)


# possible votes

upg_lock = Variable() # network upgrade lock only one update can be performed
upg_pepper = Variable()

init_time = Variable()
today = Variable()
window = Variable()


mn_vote = Variable()
dl_vote = Variable()

tot_mn = Variable()
tot_dl = Variable()

# Results
upg_consensus = Variable()


@construct
def seed():
    upg_lock.set(False)
    upg_consensus.set(False)
    mn_vote.set(0)
    dl_vote.set(0)
    tot_mn.set(0)
    tot_dl.set(0)




@export
def trigger_upgrade(pepper, initiator_vk):
    if upg_lock.get() is True:
        if check_window() is False:
            reset_contract(initiator_vk)
        else:
            return

    # for now only master's trigger upgrade
    if initiator_vk in election_house.current_value_for_policy('masternodes'):
        upg_lock.set(True)
        init_time.set(date.today())
        upg_pepper.set(pepper)
        window.set(7) #1 week 7 * 24 * 60 * 60
        mn_vote.set(0)
        dl_vote.set(0)
        #assert election_house.current_value_for_policy('masternodes')

        mnum = len(election_house.current_value_for_policy('masternodes'))
        dnum = len(election_house.current_value_for_policy('delegates'))

        tot_mn.set(mnum)
        tot_dl.set(dnum)

@export
def vote(vk):
    if upg_lock.get() is True:
        if vk in election_house.current_value_for_policy('masternodes'):
            mn_vote.set(mn_vote.get() + 1)
        if vk in election_house.current_value_for_policy('delegates'):
            dl_vote.set(dl_vote.get() + 1)

        # if now - init_time.get() >= window.get():
        #     reset_contract()
        
        check_vote_state()
    else:
        assert 'no active upgrade'


def check_vote_state():

    all_nodes = tot_mn.get() + tot_dl.get()
    all_votes = mn_vote.get() + dl_vote.get()

    if all_votes > (all_nodes * 2/3):
        upg_consensus.set(True)

def reset_contract(vk):
    if vk in election_house.current_value_for_policy('masternodes'):
        if upg_lock.get() is True:
            init_time.set(None)
            upg_consensus.set(False)
            upg_lock.set(False)

            mn_vote.set(0)
            dl_vote.set(0)
            tot_mn.set(0)
            tot_dl.set(0)

def check_window():

    today.set(date.today())
    if today.get() - init_time.get() > window.get():
        return False
    else:
        return True
    

def assert_parallel_upg_check():
    assert 'Upgrade under way. Cannot initiate parallel upgrade'
