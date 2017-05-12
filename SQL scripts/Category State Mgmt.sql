--
-- Category State management
--

DROP PROCEDURE IF EXISTS sp_category_state_mgmt;
CREATE PROCEDURE imageimprov.`sp_category_state_mgmt`()
BEGIN
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
  
  set @dtNow                = CURRENT_TIMESTAMP();

  -- Uploading runs from 'start_date' -> 'start_date + duration_upload'
  -- Voting runs from 'start_date + duration_upload' -> 'start_date + duration_upload + duration_vote'
  -- Counting runs from 'start_date + duration_upload + duration_vote' to 'start_date + duration_upload + duration_vote +24 hours'
  
  -- !CLOSED -> COUNTING
  UPDATE category set state = @COUNTING, last_updated = @dtNow
  WHERE state <> @CLOSED AND
        @dtNow > DATE_ADD(start_date, INTERVAL (category.duration_upload + category.duration_vote) HOUR) AND
        @dtNow < DATE_ADD(start_date, INTERVAL (category.duration_upload + category.duration_vote + 24) HOUR) AND
        state <> @COUNTING;
  
  -- !CLOSED -> VOTING
  UPDATE category set state = @VOTING, last_updated = @dtNow
  WHERE state <> @CLOSED and 
        @dtNow > DATE_ADD(start_date, INTERVAL (category.duration_upload) HOUR) AND
        @dtNow < DATE_ADD(start_date, INTERVAL (category.duration_upload + category.duration_vote) HOUR) AND
        state <> @VOTING;
  
  -- IDLE -> UPLOADING
  UPDATE category set state = @UPLOADING, last_updated = @dtNow
  WHERE state = @UNKNOWN and 
        @dtNow > start_date AND
        @dtNow < DATE_ADD(start_date, INTERVAL category.duration_upload HOUR) AND
        state <> @UPLOADING;
 
  -- finally, close out any errant categories with bogus states
  -- x -> CLOSED
  UPDATE category set state = @CLOSED, last_updated = @dtNow
  where state <> @CLOSED AND 
        @dtNow >DATE_ADD(start_date, INTERVAL (category.duration_upload + category.duration_vote + 24) HOUR);

END;

-- wrap in transaction so we can preview the effect
START TRANSACTION;
  CALL sp_active_categories();
  SELECT * FROM category;

  CALL sp_category_state_mgmt();

  SELECT * FROM category;
  CALL sp_active_categories();
ROLLBACK;

