import currency

owner = Variable()

@construct
def seed(vk: str):
    owner.set(vk)

@export
def withdraw(amount: int):
    assert ctx.caller == owner.get(), 'Not owner!'
    currency.transfer(amount, ctx.caller)

@export
def change_owner(vk: str):
    assert ctx.caller == owner.get(), 'Not owner!'
    owner.set(vk)
