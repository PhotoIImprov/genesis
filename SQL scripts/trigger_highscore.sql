DROP TRIGGER IF EXISTS highscores;
CREATE TRIGGER highscores
AFTER UPDATE
  ON photo FOR EACH ROW
BEGIN
  CALL sp_updateleaderboard(NEW.user_id, NEW.category_id, NEW.likes, NEW.times_voted, NEW.score);
END;
