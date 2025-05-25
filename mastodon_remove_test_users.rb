User.where("email LIKE ?", "%@test.com").find_each do |user|
  puts "Deleting user #{user.email}..."

  begin
    account = user.account

    account.statuses.destroy_all
    account.mentions.destroy_all
    account.notifications.destroy_all
    account.favourites.destroy_all
    account.blocks.destroy_all
    account.follow_requests.destroy_all
    account.followers.destroy_all
    account.following.destroy_all
    account.conversations.destroy_all

    Doorkeeper::AccessToken.where(resource_owner_id: user.id).destroy_all
    Doorkeeper::AccessGrant.where(resource_owner_id: user.id).destroy_all

    account.destroy!
    user.destroy!

    puts "Deleted user and account: #{user.email}"
  rescue => e
    puts "Failed to delete #{user.email}: #{e.message}"
  end
end
