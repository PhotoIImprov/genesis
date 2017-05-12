
-- Our stored procedure that will determine when to advance to round #2 voting
DROP PROCEDURE IF EXISTS imageimprov.sp_advance_category_round2;
CREATE PROCEDURE imageimprov.sp_advance_category_round2()
this_proc: BEGIN

  set @UNKNOWN   = 0;   -- all categories that haven't run are in this state
  set @UPLOADING = 1;   -- this category is accepting photo uploads
  set @VOTING    = 2;   -- this category can now be voted on
  set @COUNTING  = 3;   -- this cateogry done voting, needs to be finalized
  set @CLOSED    = 4;   -- done with this category, results have been tabulated
  set @ROUND1    = 0;
  set @ROUND2    = 1;
  set @ROUND2_THRESHOLD = 3; -- need at least 3 votes per photo to move to round 2
  
  -- We need to determine if any of our voting categories 
  -- need to advance to round #2
  if not exists(select * from category where state = @VOTING and round = @ROUND1) THEN
    LEAVE this_proc;
  end if;
  
  -- to make the SQL easier & clearer, we populate
  -- a "temporary" table.
  
  CREATE TABLE IF NOT EXISTS 
  scratch_round2_suspects (cid int not null, avg_votes int not null);

  insert into scratch_round2_suspects (cid, avg_votes)
    select c.id as 'category', 
    avg ((select count(be.id) from ballotentry be where be.photo_id = p.id) ) as 'avg votes'
    from photo p
    inner join category c on c.id = p.category_id
    where c.state = @VOTING AND c.round = @ROUND1
    group by c.id;

  -- We have 2 rules for moving to round #2
  --
  -- 1) The photos in this category have been voted on a threshold # of times
  -- 2) We are at least xx% through the voting period, so we need to converge on a winner
  --
  UPDATE category set round = @ROUND2
  where id in (select cid from scratch_round2_suspects where avg_votes >= @ROUND2_THRESHOLD);

  -- Also transition categories to round2 if they are getting 
  -- close to finishing
  set @dtNow = CURRENT_TIMESTAMP();
  set @VOTE_TIME_THRESHOLD = 0.75; -- if we are more than 75% through voting, time advance round
  UPDATE category set round = @ROUND2
  where round = @ROUND1 and state = @VOTING and
  @dtNow > DATE_ADD(start_date, INTERVAL (category.duration_upload + category.duration_vote * @VOTE_TIME_THRESHOLD) HOUR) AND
  @dtNow < DATE_ADD(start_date, INTERVAL (category.duration_upload + category.duration_vote) HOUR);

  truncate table scratch_round2_suspects;
  
END;

DROP PROCEDURE IF EXISTS imageimprov.sp_test_round2;
CREATE PROCEDURE imageimprov.sp_test_round2()
BEGIN
  set @VOTING = 2;
  set @ROUND1 = 0;
  set @ROUND2 = 1;
  set @dtNow = CURRENT_TIMESTAMP();
  set @upload_duration = 24;   -- 24 hours
  set @voting_duration = 72;   -- 72 hours
  set @threshold = 0 - (@upload_duration + 0.8 * @voting_duration);
  set @dtStart = DATE_ADD(@dtNow, INTERVAL @threshold HOUR);

  select * from category where round = @ROUND1 and state = @VOTING;
  update category set start_date = @dtStart, duration_upload = @upload_duration, duration_vote = @voting_duration
  where round = @ROUND1 and state = @VOTING;
  select * from category where round = @ROUND1 and state = @VOTING;
  
END;

start transaction;
  CALL sp_test_round2();

  select c.id as 'category', 
  count(p.id) as 'num photos', 
  avg ((select count(be.id) from ballotentry be where be.photo_id = p.id) ) as 'avg votes'
  from photo p
  inner join category c on c.id = p.category_id
  group by c.id;

  select id, state, `round`, start_date, duration_upload, duration_vote from category where id in (select distinct(category_id) from photo) and state = 2;
  
  CALL sp_advance_category_round2();
  
  select id, state, `round` from category where id in (select distinct(category_id) from photo) and state = 2;
  update category set round = 0 where round <> 0;
rollback;

-- update category set duration_vote = 72 where state = 0;
select * from category;

