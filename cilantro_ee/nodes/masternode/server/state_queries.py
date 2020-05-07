from cilantro_ee.storage import BlockchainDriver


def get_nonce(processor, sender, driver: BlockchainDriver):
    # get pe

    pending_nonce = driver.get_pending_nonce(processor, sender)

    pass

# Get the Nonce of a VK
    async def get_nonce(self, request, vk):
        # Might have to change this sucker from hex to bytes.
        pending_nonce = self.driver.get_pending_nonce(processor=self.wallet.verifying_key(), sender=bytes.fromhex(vk))

        log.info('Pending nonce: {}'.format(pending_nonce))

        if pending_nonce is None:
            nonce = self.driver.get_nonce(processor=self.wallet.verifying_key(), sender=bytes.fromhex(vk))
            log.info('Pending nonce was none so got nonce which is {}'.format(nonce))
            if nonce is None:
                pending_nonce = 0
                log.info('Nonce was now so pending nonce is now zero.')
            else:
                pending_nonce = nonce
                log.info('Nonce was not none so setting pending nonce to it.')

        # nonce = self.driver.get_nonce(self.wallet.verifying_key(), bytes.fromhex(vk)) or 0
        #
        # pending_nonce = self.driver.get_pending_nonce(self.wallet.verifying_key(), bytes.fromhex(vk)) or nonce

        return response.json({'nonce': pending_nonce, 'processor': self.wallet.verifying_key().hex(), 'sender': vk})

# Get all Contracts in State (list of names)
    async def get_contracts(self, request):
        contracts = self.client.get_contracts()
        return response.json({'contracts': contracts})

# Get the source code of a specific contract
    async def get_contract(self, request, contract):
        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404)
        return response.json({'name': contract, 'code': contract_code}, status=200)

    async def get_methods(self, request, contract):
        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404)

        tree = ast.parse(contract_code)

        function_defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]

        funcs = []
        for definition in function_defs:
            func_name = definition.name
            kwargs = [arg.arg for arg in definition.args.args]

            funcs.append({'name': func_name, 'arguments': kwargs})

        return response.json({'methods': funcs}, status=200)

    async def get_variables(self, request, contract):
        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404)

        tree = ast.parse(contract_code)

        assigns = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)]

        variables = []
        hashes = []

        for assign in assigns:
            if type(assign.value) == ast.Call:
                if assign.value.func.id == 'Variable':
                    variables.append(assign.targets[0].id.lstrip('__'))
                elif assign.value.func.id == 'Hash':
                    hashes.append(assign.targets[0].id.lstrip('__'))

        return response.json({
            'variables': variables,
            'hashes': hashes
        })

    async def get_variable(self, request, contract, variable):
        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404)

        key = request.args.get('key')
        if key is not None:
            key = key.split(',')

        k = self.client.raw_driver.make_key(contract=contract, variable=variable, args=key)
        value = self.client.raw_driver.get(k)

        if value is None:
            return response.json({'value': None}, status=404)
        else:
            return response.json({'value': value}, status=200, dumps=encode)

    async def iterate_variable(self, request, contract, variable):
        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404)

        key = request.args.get('key')
        # if key is not None:
        #     key = key.split(',')

        k = self.client.raw_driver.make_key(key=contract, field=variable, args=key)

        values = self.client.raw_driver.iter(k, length=500)

        if len(values) == 0:
            return response.json({'values': None}, status=404)
        return response.json({'values': values, 'next': values[-1][0]}, status=200)