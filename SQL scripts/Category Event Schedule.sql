--
-- Create Catalog Management Scheduled task
--

DROP EVENT IF EXISTS event_category_mgmt;

CREATE EVENT event_category_mgmt
  ON SCHEDULE EVERY 5 MINUTE
  DO
    CALL imageimprov.sp_category_state_mgmt();
    

select * from mysql.event;

-- Now schedule it to run

DROP EVENT IF EXISTS event_round2_trigger;

CREATE EVENT event_round2_trigger
  ON SCHEDULE EVERY 10 MINUTE
  DO
    CALL imageimprove.sp_advance_category_round2();
    
select * from mysql.event;

