"""the controller for the ballot & voting model. """
import errno
import json
from random import shuffle
from sqlalchemy import exists
from sqlalchemy import func
from logsetup import logger, timeit
from dbsetup import Configuration
from models import usermgr, category, event, engagement, photo, voting
from controllers import RewardMgr

class BallotManager:
    """
    Ballot Manager
    This class is responsible to creating our voting ballots
    """

    _ballot = None

    def string_key_to_boolean(self, d: dict, keyname: str) -> int:
        """
        if key is not present, return a '0'
        if key is any value other than '0', return '1'
        :param dict:
        :param keyname:
        :return: 0/1
        """
        if keyname in d.keys():
            str_val = d[keyname]
            if str_val != '0':
                return 1
        return 0

    def create_ballotentry_for_tags(self, session, be_dict: dict) -> list:
        try:
            if 'tags' in be_dict.keys():
                bid = be_dict['bid']
                tags = be_dict['tags']
                be_tags = voting.BallotEntryTag(bid=bid, tags=tags)
                session.add(be_tags)
                return tags
        except Exception as e:
            logger.exception(msg="error while writing ballotentrytag")
            raise
        return None

    _BADGES_FOR_VOTING = [(1,1), (25,2), (100,5)]
    def badges_for_votes(self, session, uid: int) -> (int, int):
        # let's determine if the user has earned any badges for this vote
        # (Note: the current vote hasn't been cast yet)
        try:
            q = session.query(func.count(voting.Ballot.user_id)).filter(voting.Ballot.user_id == uid)
            num_votes = q.scalar()
            # note: this is an ordered list!!
            for i in range(0, len(self._BADGES_FOR_VOTING)):
                threshold, badge_award = self._BADGES_FOR_VOTING[i]
                if threshold == num_votes:
                    return threshold, badge_award
                if threshold > num_votes: # early exit
                    break
            return 0, 0

        except Exception as e:
            logger.exception(msg="error getting badges for votes for user {}".format(uid))
            raise

    def update_rewards_for_vote(self, session, anonymous_user: usermgr.AnonUser) -> None:
        """
        Update the rewards information for this user as a result of this vote
        :param session:
        :param uid:
        :return:
        """
        threshold, badges = self.badges_for_votes(session, anonymous_user.id)
        if badges > 0:
            try:
                rm = RewardMgr.RewardManager(user_id=anonymous_user.id,
                                   rewardtype=engagement.RewardType.LIGHTBULB)
                rm.create_reward(session, quantity=badges)
            except Exception as e:
                raise

        # check out consecutive days of play...from
        try:
            rm = RewardMgr.RewardManager()
            rm.check_consecutive_day_rewards(session, anonymous_user,
                                             rewardtype=engagement.RewardType.DAYSPLAYED_30)
            rm.check_consecutive_day_rewards(session, anonymous_user,
                                             rewardtype=engagement.RewardType.DAYSPLAYED_100)
        except Exception as e:
            raise
        return None

    def process_ballots(self, session, au: usermgr.AnonUser, c: category.Category, section: int, json_ballots: str) -> list:
        """
        take the JSON ballot entries and process the votes
        :param session:
        :param c: our category
        :param section: the section (if voting round #2) the ballot is in
        :param json_ballots: the ballotentries from the request
        :return: list of ballotentries, added to session, ready for commit
        """
        bel = []
        for j_be in json_ballots:
            bid = j_be['bid']
            like = self.string_key_to_boolean(j_be, 'like')
            offensive = self.string_key_to_boolean(j_be, 'offensive')

            # if there is an 'tag' specified, then create a BallotEntryTag
            # record and save it
            try:
                tags = self.create_ballotentry_for_tags(session, j_be)
            except Exception as e:
                logger.exception(msg="error while writing ballotentrytag")
                raise

            try:
                be = session.query(voting.BallotEntry).get(bid)
                be.like = like
                be.offensive = offensive
                be.vote = j_be['vote']
                score = self.calculate_score(j_be['vote'], c.round, section)
                p = session.query(photo.Photo).get(be.photo_id)
                p.score += score
                p.times_voted += 1
                bel.append(be)
            except Exception as e:
                logger.exception(msg="error while updating photo with score")
                raise

            try:
                if like or offensive or tags is not None:
                    fbm = RewardMgr.FeedbackManager(uid=au.id, pid=be.photo_id, like=like, offensive=offensive, tags=tags)
                    fbm.create_feedback(session)
            except Exception as e:
                logger.exception(msg="error while updating feedback for ballotentry")
                raise

            tm = RewardMgr.TallyMan()
            try:
                tm.update_leaderboard(session, c, p)  # leaderboard may not be defined yet!
            except:
                pass

            try:
                self.update_rewards_for_vote(session, au)
            except Exception as e:
                logger.exception(msg="error updating reward for user{0}".format(au.id))
                raise

        return bel

    def tabulate_votes(self, session, au: usermgr.AnonUser, json_ballots: list) -> list:
        """
        We have a request with a ballot of votes. We need to parse out the
        JSON and tabulate the scores.
        :param session:
        :param au: the user
        :param json_ballots: ballot information from the request
        :return: list of ballot entries
        """
        # It's possible the ballotentries are from different sections, we'll
        # score based on the first ballotentry
        try:
            logger.info(msg='tabulate_votes, json[{0}]'.format(json_ballots))
            bid = json_ballots[0]['bid']
            be = session.query(voting.BallotEntry).get(bid)
            vr = session.query(voting.VotingRound).get(be.photo_id)
            section = 0
            if vr is not None:  # sections only matter for round 2
                section = vr.section
        except Exception as e:
            if json_ballots is not None:
                msg = 'json_ballots={}'.format(json_ballots)
            else:
                msg = "json_ballots is None!"

            logger.exception(msg=msg)
            raise

        c = session.query(category.Category).get(be.category_id)
        bel = self.process_ballots(session, au, c, section, json_ballots)
        return bel  # this is for testing only, no one else cares!


    def calculate_score(self, vote: int, round: int, section: int) -> int:
        if round == 0:
            score = voting._ROUND1_SCORING[0][vote - 1]
        else:
            score = voting._ROUND2_SCORING[section][vote - 1]
        return score

    def create_ballot(self, session, user_id: int, c: category.Category, allow_upload=False) -> list:
        """
        Returns a ballot list containing the photos to be voted on.

        :param session:
        :param user_id:
        :param cid:
        :return: dictionary: error:<error string>
                             arg: ballots()
        """
        # Voting Rounds are stored in the category, 0= Round #1, 1= Round #2
        photo_list = self.create_ballot_list(session, user_id, c, allow_upload)
        self.update_votinground(session, c, photo_list)
        return self.add_photos_to_ballot(session, user_id, c, photo_list)


    def update_votinground(self, session, c, plist):
        if c.round == 0:
            return
        for p in plist:
            session.query(voting.VotingRound).filter(voting.VotingRound.photo_id == p.id).update(
                {"times_voted": voting.VotingRound.times_voted + 1})
        return

    def add_photos_to_ballot(self, session, uid: int, c: category.Category, plist: list) -> voting.Ballot:

        self._ballot = voting.Ballot(c.id, uid)
        session.add(self._ballot)

        # now create the ballot entries and attach to the ballot
        for p in plist:
            be = voting.BallotEntry(user_id=p.user_id, category_id=c.id, photo_id=p.id)
            self._ballot.append_ballotentry(be)
            session.add(be)
            # see if the user has "liked" this photo
            fb = engagement.Feedback.get_feedback(session, pid=p.id, uid=uid)
            if fb is not None:
                be.like = fb.like
                be.offensive = fb.offensive

        return self._ballot


    def read_photos_by_ballots_round2(self, session, uid: int, current_category: category.Category, num_votes: int,
                                      count: int) -> list:
        """return a list of photos that qualify for the next round of balloting
        for the specified category"""

        # *****************************
        # **** CONFIGURATION ITEMS ****
        num_sections = voting._NUM_SECTONS_ROUND2  # the "stratification" of the photos that received votes or likes
        max_votes = voting._ROUND2_TIMESVOTED  # The max # of votes we need to pick a winner
        # ****************************

        # create an array of our sections
        section_list = []
        for idx in range(num_sections):
            section_list.append(idx)

        ballot_photo_list = []
        shuffle(section_list)  # randomize the section list
        oversize = count * 20
        for section in section_list:
            query = session.query(photo.Photo).filter(photo.Photo.user_id != uid). \
                filter(photo.Photo.category_id == current_category.id). \
                filter(photo.Photo.active == 1). \
                join(voting.VotingRound, voting.VotingRound.photo_id == photo.Photo.id). \
                filter(voting.VotingRound.section == section). \
                filter(voting.VotingRound.times_voted == num_votes).limit(oversize)
            photo_list = query.all()
            ballot_photo_list.extend(photo_list)  # accumulate ballots we've picked, can save us time later
            # see if we encountered 4 in our journey
            if len(ballot_photo_list) >= count:
                return ballot_photo_list

        # we tried everything, let's just grab some photos from any section (HOW TO RANDOMIZE THIS??)
        if num_votes == voting._MAX_VOTING_ROUNDS:
            for section in section_list:
                query = session.query(photo.Photo).filter(photo.Photo.user_id != uid). \
                    filter(photo.Photo.category_id == current_category.id). \
                    filter(photo.Photo.active == 1). \
                    join(voting.VotingRound, voting.VotingRound.photo_id == photo.Photo.id). \
                    filter(voting.VotingRound.section == section).limit(oversize)
                photo_list = query.all()
                ballot_photo_list.extend(photo_list)  # accumulate ballots we've picked, can save us time later
                if len(ballot_photo_list) >= count:
                    return ballot_photo_list
        return ballot_photo_list  # return what we have

    # create_ballot_list()
    # ======================
    # we will read 'count' photos from the database
    # that don't belong to this user. We loop through
    # times voted on for our first 3 passes
    #
    # if we can't get 'count' photos, then we are done
    # Round #1...
    def create_ballot_list(self, session, user_id: int, c: category.Category, allow_upload: bool) -> list:
        """

        :param session:
        :param user_id: the user asking for the ballot (so we can exclude their photos)
        :param c: category
        :return: a list of photos, '_NUM_BALLOT_ENTRIES' long. We ask for more than this,
                shuffle the result and trim the list length, so we get some randomness
        """
        if c.state != category.CategoryState.VOTING.value and not allow_upload:
            if c is not None:
                logger.error(msg='Category {0} for user {1} not in voting state'.format(json.dumps(c.to_json()), user_id))
            raise Exception(errno.EINVAL, 'category not in VOTING state')

        # we need "count"
        count = voting._NUM_BALLOT_ENTRIES
        photos_for_ballot = []
        for num_votes in range(0, voting._MAX_VOTING_ROUNDS + 1):
            if c.round == 0:
                photo_list = self.read_photos_by_ballots_round1(session, user_id, c, num_votes, count)
            else:
                photo_list = self.read_photos_by_ballots_round2(session, user_id, c, num_votes, count)

            if photo_list is not None:
                photos_for_ballot.extend(photo_list)
                if len(photos_for_ballot) >= count:
                    break

        return self.cleanup_list(photos_for_ballot, count)  # remove dupes, shuffle list

    #        return photos_for_ballot[:count]

    @timeit()
    def cleanup_list(self, photos_four_ballot: list, ballot_size: int) -> list:
        """
        We get a list of photos that are a straight pull from the
        database. We're going to shuffle it and not allow any
        duplicates based on 'thumb_hash'
        :param photos_four_ballot:
        :param ballot_size:
        :return: list of ballots of 'ballot_size', randomized & scrubbed of duplicates (if possible)
        """

        shuffle(photos_four_ballot)
        # pretty_list = []
        # for p in p4b:
        #     # we have a candidate photo, see if a copy is already in the list
        #     insert_p = True
        #     if p._photometa.thumb_hash is not None: # no hash computed, skip the check
        #         for dupe_check in pretty_list:
        #             if dupe_check._photometa.thumb_hash == p._photometa.thumb_hash:
        #                 insert_p = False
        #                 break
        #     if insert_p:
        #         pretty_list.append(p)
        #         if len(pretty_list) == ballot_size:
        #             return pretty_list

        # worst cases just return a random list
        return photos_four_ballot[:ballot_size]

    def read_photos_by_ballots_round1(self, session, user_id: int, c: category.Category, num_votes: int,
                                      count: int) -> list:
        """
        read_photos_by_ballots_round1()
        read a list of photos to construct our return ballot.

        :param session:
        :param user_id: user id that's voting, filter out photos that are their's
        :param c: category
        :param num_votes: select photos with this # of votes
        :param count: how many photos to fetch
        :return: list of Photo objects
        """

        over_size = count * 20  # ask for a lot more so we can randomize a bit
        # if ballotentry has been voted on, exclude photos the user has already seen
        if num_votes == 0:
            query = session.query(photo.Photo).filter(photo.Photo.category_id == c.id). \
                filter(photo.Photo.active == 1). \
                filter(photo.Photo.user_id != user_id). \
                filter(~exists().where(voting.BallotEntry.photo_id == photo.Photo.id)).limit(over_size)
        else:
            if num_votes == voting._MAX_VOTING_ROUNDS:
                query = session.query(photo.Photo).filter(photo.Photo.category_id == c.id). \
                    join(voting.BallotEntry, photo.Photo.id == voting.BallotEntry.photo_id). \
                    filter(photo.Photo.user_id != user_id). \
                    filter(photo.Photo.active == 1). \
                    group_by(photo.Photo.id).limit(over_size)
            else:
                query = session.query(photo.Photo).filter(photo.Photo.category_id == c.id). \
                    join(voting.BallotEntry, photo.Photo.id == voting.BallotEntry.photo_id). \
                    filter(photo.Photo.user_id != user_id). \
                    filter(photo.Photo.active == 1). \
                    group_by(photo.Photo.id). \
                    having(func.count(voting.BallotEntry.photo_id) == num_votes).limit(over_size)

        photo_list = query.all()
        return photo_list

    def active_voting_categories(self, session, user_id: int) -> list:
        """
        Only return categories that have photos that can be voted on
        :param session: database connection
        :param user_id: user id, to filter the category list to only categories the user can access
        :return: <list> of categories available to the user for voting
        """
        query = session.query(category.Category).filter(category.Category.state == category.CategoryState.VOTING.value). \
            join(photo.Photo, photo.Photo.category_id == category.Category.id). \
            outerjoin(event.EventCategory, event.EventCategory.category_id == category.Category.id). \
            outerjoin(event.EventUser, event.EventUser.event_id == event.EventCategory.event_id). \
            filter(photo.Photo.user_id != user_id). \
            filter(photo.Photo.active == 1). \
            filter((event.EventUser.user_id == user_id) | (event.EventUser.user_id == None)). \
            group_by(category.Category.id).having(func.count(photo.Photo.id) > 3)
        category_list = query.all()

        # see if the user has uploaded to the current UPLOAD category, and if they have check to see
        # if there are enough photos include it in the vote-able category list
        query = session.query(category.Category).filter(category.Category.state == category.CategoryState.UPLOAD.value). \
            join(photo.Photo, photo.Photo.category_id == category.Category.id). \
            outerjoin(event.EventCategory, event.EventCategory.category_id == category.Category.id). \
            outerjoin(event.EventUser, event.EventUser.event_id == event.EventCategory.event_id). \
            filter(photo.Photo.user_id == user_id). \
            filter(photo.Photo.active == 1). \
            filter((event.EventUser.user_id == user_id) | (event.EventUser.user_id == None)). \
            group_by(category.Category.id).having(func.count(photo.Photo.id) > 0)
        c_can_vote_on = query.all()

        if len(c_can_vote_on) > 0:
            query = session.query(category.Category).filter(category.Category.state == category.CategoryState.UPLOAD.value). \
                join(photo.Photo, photo.Photo.category_id == category.Category.id). \
                outerjoin(event.EventCategory, event.EventCategory.category_id == category.Category.id). \
                outerjoin(event.EventUser, event.EventUser.event_id == event.EventCategory.event_id). \
                filter(photo.Photo.user_id != user_id). \
                filter(photo.Photo.active == 1). \
                filter((event.EventUser.user_id == user_id) | (event.EventUser.user_id == None)). \
                group_by(category.Category.id).having(func.count(photo.Photo.id) >= Configuration.UPLOAD_CATEGORY_PICS)
            categories_uploadable = query.all()

            # only items in c_can_vote_on and also in c_upload can be voted on
            # so "AND" the lists
            categories_voteable = set(c_can_vote_on).intersection(categories_uploadable)
            if len(categories_voteable) > 0:
                set_list = list(categories_voteable)
                category_list.extend(set_list)

        return category_list
