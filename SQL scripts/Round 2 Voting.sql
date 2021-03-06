--
--
-- see if we need to update our table schema
-- 
DROP PROCEDURE IF EXISTS sp_update_tables;
CREATE PROCEDURE sp_update_tables() begin
  IF NOT EXISTS(SELECT * FROM information_schema.COLUMNS WHERE COLUMN_NAME='round' AND TABLE_NAME='category') THEN
     ALTER TABLE category ADD COLUMN round int NOT NULL DEFAULT 0;
  END IF;

  IF NOT EXISTS(SELECT * FROM information_schema.COLUMNS WHERE COLUMN_NAME='duration_upload' AND TABLE_NAME='category') THEN
     ALTER TABLE category ADD COLUMN duration_upload int NOT NULL DEFAULT 24;
  END IF;

  IF NOT EXISTS(SELECT * FROM information_schema.COLUMNS WHERE COLUMN_NAME='duration_vote' AND TABLE_NAME='category') THEN
     ALTER TABLE category ADD COLUMN duration_vote int NOT NULL DEFAULT 24;
  END IF;

  IF NOT EXISTS(SELECT * FROM information_schema.COLUMNS WHERE COLUMN_NAME='times_voted' AND TABLE_NAME='voting_round') THEN
     ALTER TABLE voting_round ADD COLUMN times_voted int NOT NULL DEFAULT 0;
  END IF;
  IF NOT EXISTS(SELECT * FROM information_schema.COLUMNS WHERE COLUMN_NAME='section' AND TABLE_NAME='voting_round') THEN
     ALTER TABLE voting_round ADD COLUMN section int NOT NULL;
  END IF;

END;

CALL sp_update_tables();
DROP PROCEDURE sp_update_tables;

DROP PROCEDURE IF EXISTS sp_simulate_photos;
CREATE PROCEDURE imageimprov.`sp_simulate_photos`(IN in_sim_size int)
BEGIN
  -- this procedure will create a lot of photo records so we can
  -- test our round #2 algorithm
  
  -- Photo records are simple
  -- (id, user_id, category_id, filepath, filename, times_voted, score, likes, created_date, last_updated)
  --
  -- id : autogenerated
  -- user_id: must match an anonuser record
  -- category_id: yep, need this!
  -- filepath, filename: don't care
  -- times_voted, score, likes: need these
  -- created_date, last_updated: autogenerated, and we don't care
  
  -- Here's what we'll do:
  -- Step #1: Create fake accounts with photos
  --     a) create anonymous user
  --     b) create photo record for user
  --     c) ... repeat ...
  -- 
  -- **********************************************
  --
  -- We are going to manage category state transitions
  -- we will get called frequently so we need to 
  -- change state only when needed
  -- see models/category.py/CategoryState(Enum) for mapping
  --
  set @UNKNOWN   = 0;   -- all categories that haven't run are in this state
  set @UPLOADING = 1;   -- this category is accepting photo uploads
  set @VOTING    = 2;   -- this category can now be voted on
  set @COUNTING  = 3;   -- this cateogry done voting, needs to be finalized
  set @CLOSED    = 4;   -- done with this category, results have been tabulated

  set @idx       = 0;
  set @max_users = in_sim_size;
  set @guid      = '';
  select @cid := id from category where state = @VOTING;
  select CONCAT('category_id = ', @cid);
  
  WHILE @idx < @max_users DO
    set @guid = replace(uuid(), '-', '');
    insert into anonuser(guid) values(@guid);
    set @id = LAST_INSERT_ID();
    
    set @score = FLOOR(RAND() * 100) - 50;
    set @likes = FLOOR(RAND() * 10) - 7;
    if @score < 0 THEN
      set @score = 0;
    end if;
    if @likes < 0 THEN
       set @likes = 0;
    end if;
    set @times_voted = 4;
    insert into photo (user_id, category_id, filepath, filename, times_voted, score, likes) values(@id, @cid, '/mnt/gcs-photos/foo', @guid, @times_voted, @score, @likes);
    set @idx = @idx + 1;    
  END WHILE;
  
  -- We have inserted '@max_users' records in both the anonuser table and photo table
  
END;

DROP PROCEDURE IF EXISTS sp_voting_round2;
DROP PROCEDURE IF EXISTS sp_initialize_round2;
CREATE PROCEDURE imageimprov.`sp_initialize_round2`(IN in_section_size int, IN in_cid int)
BEGIN

  set @cid = 0;
  set @photos_to_consider = 0;
  --
  -- We are going to manage category state transitions
  -- we will get called frequently so we need to 
  -- change state only when needed
  -- see models/category.py/CategoryState(Enum) for mapping
  --
  set @UNKNOWN   = 0;   -- all categories that haven't run are in this state
  set @UPLOADING = 1;   -- this category is accepting photo uploads
  set @VOTING    = 2;   -- this category can now be voted on
  set @COUNTING  = 3;   -- this cateogry done voting, needs to be finalized
  set @CLOSED    = 4;   -- done with this category, results have been tabulated

  if in_cid is NULL then
    select @cid := id from category where state = @VOTING;
  else
    set @cid = in_cid;
  end if;
  
  select CONCAT('category id = ', @cid);
  
  -- Now we need to compute how many photos have votes or likes
  select @photos_to_consider := count(*) from photo where category_id = @cid AND
  (score > 0 or likes > 0);
  select CONCAT('Photos to consider = ', @photos_to_consider);
  
  -- Okay we have identified photos that need a 2nd round of voting
  
  set @NUM_SECTIONS = in_section_size; -- how many divisions for the 2nd round
  set @SIZE_SECTIONS = FLOOR(@photos_to_consider / @NUM_SECTIONS);
  
  select CONCAT('Computed section size is ', @SIZE_SECTIONS); 
  
  set @section_idx = 0;
  set @photos_remaining = @photos_to_consider;
   
  WHILE @section_idx < @NUM_SECTIONS DO
    -- Okay, move each "section" to our new table
    select @section_idx as 'pass #';
    
    PREPARE s FROM
    'INSERT INTO voting_round (photo_id, section, times_voted)
    SELECT id, @section_idx, 0 from photo p 
    WHERE p.category_id = ? and (p.score <> 0 OR p.likes <> 0) and not exists (select * from voting_round vr where vr.photo_id = p.id)
    ORDER by p.score desc, p.likes desc LIMIT ?;';
    EXECUTE s USING @cid, @SIZE_SECTIONS;
    
    set @photos_remaining = @photos_remaining - @SIZE_SECTIONS;
    set @section_idx = @section_idx + 1;
    -- during the last section, adjust for uneveness of sections
    if @section_idx = @NUM_SECTIONS - 1 THEN
       set @SIZE_SECTIONS = @photos_remaining;
       select CONCAT('final section size = ', @SIZE_SECTIONS);
    end if;
  END WHILE;
  
  # now our category is ready for round 2 voting!
  update category set round = 1 where id = @cid;
  
END;

DROP PROCEDURE IF EXISTS sp_get_round2_ballot;
CREATE PROCEDURE imageimprov.`sp_get_round2_ballot`(IN in_cid int, IN in_section int)
BEGIN

  if in_cid is NULL then
    select @cid := id from category where state = @VOTING;
  else
    set @cid = in_cid;
  end if;
  
  if in_section is NULL then
    set @section = FLOOR(RAND() * 8); -- random value 0-7
  else
    set @section = in_section;
  end if;

  set @str_out = CONCAT('category_id = ', @cid);
  set @str_out = CONCAT(@str_out, CONCAT(', section =', @section) );
  select @str_out;

  -- Okay select 4 from the strata we picked
  CREATE TEMPORARY TABLE IF NOT EXISTS round2_rows AS 
  select vr.photo_id, vr.section from voting_round vr
   inner join photo p on p.id = vr.photo_id
   where p.category_id = @cid and vr.section = @section
   LIMIT 4;

  INSERT INTO round2_rows 
  select vr.photo_id, vr.section from voting_round vr
  inner join photo p on p.id = vr.photo_id
  where p.category_id = @cid and vr.section = @section
  LIMIT 4;

  -- this is just so subsequent calls get different values
  update voting_round vr
  set vr.times_voted = vr.times_voted + 1
  where vr.photo_id in (select photo_id from round2_rows);

  -- Don't need this anymore
  select * from round2_rows;
  truncate table round2_rows;
  
END;

select count(*) as 'number before simulation' from photo where category_id = 2123;
start transaction;
  CALL sp_simulate_photos(10000);
  select count(*) as 'number simulated' from photo where category_id = 2123;
  select count(*) from anonuser;
  call sp_initialize_round2(8, null);
  
  select count(*) from voting_round;
  select section, count(section) from voting_round group by section;
  
  CALL sp_get_round2_ballot(null, null); -- let subroutine pick
  CALL sp_get_round2_ballot(null, null); -- let subroutine pick
  CALL sp_get_round2_ballot(null, null); -- let subroutine pick
 
 --  select vr.section, vr.photo_id, p.category_id, p.score, p.likes from voting_round vr
 --  inner join photo p on p.id = vr.photo_id
 --  order by p.score desc, p.likes desc;
rollback;
