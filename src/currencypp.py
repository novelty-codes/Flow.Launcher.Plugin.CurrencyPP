import traceback
from exchange import ExchangeRates, UpdateFreq, CurrencyError
from flox.utils import cache_path
from parsy import ParseError
from parser import make_parser, ParserProperties
from flox import Flox, clipboard


class CurrencyPP(Flox):

    broker = None

    def __init__(self):
        super().__init__()
        # self.logger_level("debug")
        self._read_config()

        # actions = [
        #     self.create_action(
        #         name=self.ACTION_COPY_RESULT,
        #         label="Copy result with code",
        #         short_desc="Copy result (with code) to clipboard"),
        #     self.create_action(
        #         name=self.ACTION_COPY_AMOUNT,
        #         label="Copy numerical result",
        #         short_desc="Copy numerical result to clipboard"),
        #     self.create_action(
        #         name=self.ACTION_COPY_EQUATION,
        #         label="Copy conversion",
        #         short_desc="Copy conversion equation to clipboard")]

        # self.set_actions(self.ITEMCAT_RESULT, actions)

    def query(self, user_input):
        try:
            query = self._parse_and_merge_input(user_input, True)
            # This tests whether the user entered enough information to
            # indicate a currency conversion request.
            if not self._is_direct_request(query):
                return
            # if the conversion would have failed, return now
            self.broker.convert(self._parse_and_merge_input(user_input))
        except CurrencyError:
            return
        except Exception as e:
            # self.logger.error("convert error:\n" +
            #                   "\n".join(traceback.format_exception(e)))
            return

        try:
            query = self._parse_and_merge_input(user_input)
            if query['destinations'] is None or query['sources'] is None:
                return

            if self.broker.tryUpdate():
                self._update_update_item()

            if self.broker.error:
                self.add_item("Webservice failed",
                              '{}'.format(self.broker.error))
            else:
                results = self.broker.convert(query)

                for result in results:
                    self.add_item(
                        result['title'],
                        result['description'],
                        context=result['description'],
                        method=self.item_action,
                        parameters=[result['amount']],
                        score=100,
                    )
        except Exception as exc:
            self.add_item("query", "Error: " + str(exc))

        self.add_item(
            'Update Currency',
            'Last updated at ' + self.broker.last_update.isoformat(),
            method=self.update_rates,
            parameters=[user_input],
            dont_hide=True
        )

    def item_action(self, amount):
        clipboard.put(str(amount))

    def update_rates(self, last_query):
        self.broker.update()
        self.change_query(str(last_query), True)

    def _is_direct_request(self, query):
        entered_dest = ('destinations' in query and
                        query['destinations'] is not None)
        entered_source = (query['sources'] is not None and
                          len(query['sources']) > 0 and
                          query['sources'][0]['currency'] is not None)

        return entered_dest or entered_source

    def _parse_and_merge_input(self, user_input=None, empty=False):
        if empty:
            query = {'sources': None}
        else:
            query = {
                'sources': [{'currency': self.broker.default_cur_in, 'amount': 1.0}],
                'destinations': [{'currency': cur} for cur in self.broker.default_curs_out],
                'extra': None
            }

        if not user_input:
            return query

        user_input = user_input.lstrip()

        try:
            parsed = self.parser.parse(user_input)
            if not parsed['destinations'] and 'destinations' in query:
                parsed['destinations'] = query['destinations']
            return parsed
        except ParseError:
            return query

    def _read_config(self):
        def _warn_cur_code(name, fallback):
            fmt = "Invalid {} value in config. Falling back to default: {}"
            self.logger.warning(fmt.format(name, fallback))

        self.update_freq = UpdateFreq(self.settings.get('update_freq'))

        app_id_key = self.settings.get('app_id').strip()

        cache_dir = cache_path(self.name)
        cache_dir.mkdir(exist_ok=True)
        self.broker = ExchangeRates(
            cache_dir, self.update_freq, app_id_key, self)

        input_code = self.settings.get('input_cur').strip()
        validated_input_code = self.broker.set_default_cur_in(input_code)

        if not validated_input_code:
            _warn_cur_code("input_cur", self.broker.default_cur_in)

        output_code = self.settings.get('output_cur').strip()
        validated_output_code = self.broker.set_default_curs_out(output_code)

        if not validated_output_code:
            _warn_cur_code("output_cur", self.broker.default_curs_out)

        # separators
        separators_string = self.settings.get('separators').strip()
        separators = separators_string.split()

        # destination_separators
        dest_seps_string = self.settings.get('destination_separators').strip()
        dest_separators = dest_seps_string.split()

        # aliases
        self.broker.clear_aliases()

        aliases_string = self.settings.get('aliases')

        for line in aliases_string.splitlines():
            try:
                key, aliases_string = line.split('=')
                key = key.strip()
                aliases_string = aliases_string.strip()

                validatedKey = self.broker.validate_code(key)
                aliases = aliases_string.split()

                for alias in aliases:
                    validated = self.broker.validate_alias(alias)
                    if validated:
                        self.broker.add_alias(validated, validatedKey)
                    else:
                        self.logger.warning(
                            'Alias {} is invalid. It will be ignored'.format(alias))
            except Exception:
                self.logger.warning(
                    'Key {} is not a valid currency. It will be ignored'.format(key))

        properties = ParserProperties()
        properties.to_keywords = separators
        properties.sep_keywords = dest_separators
        self.parser = make_parser(properties)


if __name__ == "__main__":
    CurrencyPP()
