DROP PROCEDURE IF EXISTS sp_updateleaderboard;
DELIMITER //
CREATE PROCEDURE sp_updateleaderboard (IN in_uid int, IN in_cid int, IN in_likes int, IN in_vote int, IN in_score int)
this_proc: BEGIN
  declare leaderboard_size int;
  declare num_leaders int;
  declare uid int;
  declare min_score int;
  
  # IF (in_uid is NULL OR in_cid is NULL) THEN
  #    LEAVE this_proc;
  # END IF;
    
  set leaderboard_size = 5; -- we should get this from somewhere global...

  -- The userboard isn't full, add the user (need to ensure we don't add more than 'num_leaders' due to race condition)
  select count(*) into num_leaders from leaderboard where category_id = in_cid;

  -- Case #1: User is already on the leaderboard, update their record!
  -- User already on leaderboard, update and leave
  IF EXISTS(select * from leaderboard where user_id = in_uid AND category_id = in_cid) THEN
      UPDATE leaderboard set score = in_score, likes = in_likes, votes = in_vote
      where user_id = in_uid AND category_id = in_cid;
      
      IF (ROW_COUNT() = 1) THEN -- race condition test
        LEAVE this_proc;
      END IF;
  END IF;


  -- Case #2: The leaderboard is full and we have a score that belongs on it (user is NOT on leaderboard due to Case #1)
  IF (num_leaders >= leaderboard_size) AND EXISTS(select * from leaderboard where score < in_score and category_id = in_cid) THEN
    -- identify the row we're going to swap with
    SELECT MIN(score) into min_score FROM leaderboard where category_id = in_cid;
    SELECT user_id into uid FROM leaderboard where category_id = in_cid AND score = min_score LIMIT 1;
    IF (ROW_COUNT() = 0) THEN -- race condition, score changed before we could get user_id
      LEAVE this_proc;
    END IF;
    
    -- uid/min_score is the current record with the lowest score, overwrite!  
    IF (in_score > min_score) THEN
      UPDATE leaderboard set user_id = in_uid, score = in_score, votes = in_vote, likes = in_likes
      WHERE category_id = in_cid AND user_id = uid AND min_score = score;
      
      -- If no rows affected, then race condition, regardless we are done here
      LEAVE this_proc;
    END IF;
  END IF;
  
  -- Case #3: Leader board is not full (user is NOT on leaderboard due to Case #1)
  IF (num_leaders < leaderboard_size) THEN
    -- okay we don't have a full leaderboard
    INSERT INTO leaderboard (score, likes, votes, user_id, category_id) VALUES(in_score, in_likes, in_vote, in_uid, in_cid);
    IF (ROW_COUNT() = 1) THEN -- race condition test
      LEAVE this_proc;
    END IF;
  END IF;

END //
DELIMITER ;
