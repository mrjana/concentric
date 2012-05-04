import boto

def aws_upload(bucket_name, key_name, file_path):
	s3 = boto.connect_s3()
	bucket = s3.create_bucket(bucket_name)  # bucket names must be unique
	key = bucket.new_key(key_name)
	key.set_contents_from_filename(file_path)
	key.set_acl('public-read')

def aws_download(bucket_name, key_name, file_path):
	s3 = boto.connect_s3()
	key = s3.get_bucket(bucket_name).get_key(key_name)
	key.get_contents_to_filename(file_path)