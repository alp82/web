# -*- coding: utf-8 -*-
"""Define the management command to assemble leaderboard rankings.

Copyright (C) 2018 Gitcoin Core

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.

"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.models import Bounty, Profile, Tip
from marketing.models import LeaderboardRank

IGNORE_PAYERS = []
IGNORE_EARNERS = ['owocki']  # sometimes owocki pays to himself. what a jerk!

days_back = 7
if settings.DEBUG:
    days_back = 30
weekly_cutoff = timezone.now() - timezone.timedelta(days=days_back)
monthly_cutoff = timezone.now() - timezone.timedelta(days=30)
quarterly_cutoff = timezone.now() - timezone.timedelta(days=90)
yearly_cutoff = timezone.now() - timezone.timedelta(days=365)


def profile_to_location(handle):
    profiles = Profile.objects.filter(handle__iexact=handle)
    if handle and profiles.exists():
        profile = profiles.first()
        return profile.locations
    return []


def bounty_to_location(bounty):
    locations = profile_to_location(bounty.bounty_owner_github_username)
    fulfiller_usernames = list(bounty.fulfillments.filter(accepted=True).values_list('fulfiller_github_username', flat=True))
    for username in fulfiller_usernames:
        locations = locations + locations
    return locations


def tip_to_location(tip):
    return profile_to_location(tip.username) + profile_to_location(tip.from_username)


def tip_to_country(tip):
    return list(set([ele['country_name'] for ele in tip_to_location(tip) if ele and ele['country_name']]))


def bounty_to_country(bounty):
    return list(set([ele['country_name'] for ele in bounty_to_location(bounty) if ele and ele['country_name']]))


def tip_to_continent(tip):
    return list(set([ele['continent_name'] for ele in tip_to_location(tip) if ele and ele['continent_name']]))


def bounty_to_continent(bounty):
    return list(set([ele['continent_name'] for ele in bounty_to_location(bounty) if ele and ele['continent_name']]))


def tip_to_city(tip):
    return list(set([ele['city'] for ele in tip_to_location(tip) if ele and ele['city']]))


def bounty_to_city(bounty):
    return list(set([ele['city'] for ele in bounty_to_location(bounty) if ele and ele['city']]))


def default_ranks():
    """Generate a dictionary of nested dictionaries defining default ranks.

    Returns:
        dict: A nested dictionary mapping of all default ranks with empty dicts.

    """
    times = ['all', 'weekly', 'quarterly', 'yearly', 'monthly']
    breakdowns = ['fulfilled', 'all', 'payers', 'earners', 'orgs', 'keywords', 'tokens', 'countries', 'cities', 'continents']
    return_dict = {}
    for time in times:
        for bd in breakdowns:
            key = f'{time}_{bd}'
            return_dict[key] = {}

    return return_dict

ranks = default_ranks()
counts = default_ranks()


def add_element(key, index_term, amount):
    index_term = index_term.replace('@', '')
    if not index_term or index_term == "None":
        return
    if index_term not in ranks[key].keys():
        ranks[key][index_term] = 0
    if index_term not in counts[key].keys():
        counts[key][index_term] = 0
    ranks[key][index_term] += round(float(amount), 2)
    counts[key][index_term] += 1


def sum_bounty_helper(b, breakdown, index_term, val_usd):
    fulfiller_index_terms = list(b.fulfillments.filter(accepted=True).values_list('fulfiller_github_username', flat=True))
    add_element(f'{breakdown}_all', index_term, val_usd)
    add_element(f'{breakdown}_fulfilled', index_term, val_usd)
    if index_term == b.bounty_owner_github_username and index_term not in IGNORE_PAYERS:
        add_element(f'{breakdown}_payers', index_term, val_usd)
    if index_term == b.org_name and index_term not in IGNORE_PAYERS:
        add_element(f'{breakdown}_orgs', index_term, val_usd)
    if index_term in fulfiller_index_terms and index_term not in IGNORE_EARNERS:
        add_element(f'{breakdown}_earners', index_term, val_usd)
    if b.token_name == index_term:
        add_element(f'{breakdown}_tokens', index_term, val_usd)
    if index_term in bounty_to_country(b):
        add_element(f'{breakdown}_countries', index_term, val_usd)
    if index_term in bounty_to_city(b):
        add_element(f'{breakdown}_cities', index_term, val_usd)
    if index_term in bounty_to_continent(b):
        add_element(f'{breakdown}_continents', index_term, val_usd)
    if index_term in b.keywords_list:
        is_github_org_name = Bounty.objects.filter(github_url__icontains=f'https://github.com/{index_term}').exists()
        is_github_repo_name = Bounty.objects.filter(github_url__icontains=f'/{index_term}/').exists()
        index_keyword = not is_github_repo_name and not is_github_org_name
        if index_keyword:
            add_element(f'{breakdown}_keywords', index_term, val_usd)


def sum_bounties(b, index_terms):
    val_usd = b._val_usd_db
    for index_term in index_terms:
        if b.idx_status == 'done':
            breakdown = 'all'
            sum_bounty_helper(b, breakdown, index_term, val_usd)
            ###############################
            if b.created_on > weekly_cutoff:
                breakdown = 'weekly'
                sum_bounty_helper(b, breakdown, index_term, val_usd)
            if b.created_on > monthly_cutoff:
                breakdown = 'monthly'
                sum_bounty_helper(b, breakdown, index_term, val_usd)
            if b.created_on > quarterly_cutoff:
                breakdown = 'quarterly'
                sum_bounty_helper(b, breakdown, index_term, val_usd)
            if b.created_on > yearly_cutoff:
                breakdown = 'yearly'
                sum_bounty_helper(b, breakdown, index_term, val_usd)


def sum_tip_helper(t, breakdown, index_term, val_usd):
    add_element(f'{breakdown}_all', index_term, val_usd)
    add_element(f'{breakdown}_fulfilled', index_term, val_usd)
    if t.username == index_term or breakdown == 'all':
        add_element(f'{breakdown}_earners', index_term, val_usd)
    if t.from_username == index_term:
        add_element(f'{breakdown}_payers', index_term, val_usd)
    if t.org_name == index_term:
        add_element(f'{breakdown}_orgs', index_term, val_usd)
    if t.tokenName == index_term:
        add_element(f'{breakdown}_tokens', index_term, val_usd)
    if index_term in tip_to_country(t):
        add_element(f'{breakdown}_countries', index_term, val_usd)
    if index_term in tip_to_city(t):
        add_element(f'{breakdown}_cities', index_term, val_usd)
    if index_term in tip_to_continent(t):
        add_element(f'{breakdown}_continents', index_term, val_usd)


def sum_tips(t, index_terms):
    val_usd = t.value_in_usdt_now
    for index_term in index_terms:
        breakdown = 'all'
        sum_tip_helper(t, breakdown, index_term, val_usd)
        #####################################
        if t.created_on > weekly_cutoff:
            breakdown = 'weekly'
            sum_tip_helper(t, breakdown, index_term, val_usd)
        if t.created_on > monthly_cutoff:
            breakdown = 'monthly'
            sum_tip_helper(t, breakdown, index_term, val_usd)
        if t.created_on > quarterly_cutoff:
            breakdown = 'quarterly'
            sum_tip_helper(t, breakdown, index_term, val_usd)
        if t.created_on > yearly_cutoff:
            breakdown = 'yearly'
            sum_tip_helper(t, breakdown, index_term, val_usd)


def should_suppress_leaderboard(handle):
    if not handle:
        return True
    profiles = Profile.objects.filter(handle__iexact=handle)
    if profiles.exists():
        profile = profiles.first()
        if profile.suppress_leaderboard or profile.hide_profile:
            return True
    return False


class Command(BaseCommand):

    help = 'creates leaderboard objects'

    def handle(self, *args, **options):
        # get bounties
        bounties = Bounty.objects.current().filter(network='mainnet')

        # iterate
        for b in bounties:
            if not b._val_usd_db:
                continue

            index_terms = []
            if not should_suppress_leaderboard(b.bounty_owner_github_username):
                index_terms.append(b.bounty_owner_github_username)
                if b.org_name:
                    index_terms.append(b.org_name)
            for fulfiller in b.fulfillments.filter(accepted=True):
                if not should_suppress_leaderboard(fulfiller.fulfiller_github_username):
                    index_terms.append(fulfiller.fulfiller_github_username)
            for keyword in b.keywords_list:
                index_terms.append(keyword)
            for keyword in bounty_to_city(b):
                index_terms.append(keyword)
            for keyword in bounty_to_continent(b):
                index_terms.append(keyword)
            for keyword in bounty_to_country(b):
                index_terms.append(keyword)

            index_terms.append(b.token_name)

            sum_bounties(b, index_terms)

        # tips
        tips = Tip.objects.exclude(txid='').filter(network='mainnet')

        for t in tips:
            if not t.value_in_usdt_now:
                continue
            index_terms = []
            if not should_suppress_leaderboard(t.username):
                index_terms.append(t.username)
            if not should_suppress_leaderboard(t.from_username):
                index_terms.append(t.from_username)
            if not should_suppress_leaderboard(t.org_name):
                index_terms.append(t.org_name)
            if not should_suppress_leaderboard(t.tokenName):
                index_terms.append(t.tokenName)
            for keyword in tip_to_country(t):
                index_terms.append(keyword)
            for keyword in tip_to_city(t):
                index_terms.append(keyword)
            for keyword in tip_to_continent(t):
                index_terms.append(keyword)

            sum_tips(t, index_terms)

        # set old LR as inactive
        for lr in LeaderboardRank.objects.filter(active=True):
            lr.active = False
            lr.save()

        # save new LR in DB
        for key, rankings in ranks.items():
            rank = 1
            for index_term, amount in sorted(rankings.items(), key=lambda x: x[1], reverse=True):
                count = counts[key][index_term]
                LeaderboardRank.objects.create(
                    github_username=index_term,
                    leaderboard=key,
                    amount=amount,
                    count=count,
                    active=True,
                    rank=rank,
                )
                rank += 1
                print(key, index_term, amount, count, rank)
