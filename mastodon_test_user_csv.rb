require 'csv'

num_users = 500
client_id = 'YHTqsYJu26bZ1hO2J2YN6Ajx-0z4SIDIMeln0CgGx3o'
client_secret = 'RF9HsYzBxumbW3AzNLSH0jO8zhFTIRy8Xene8gDZtMI'

app = Doorkeeper::Application.find_by(uid: client_id)

if app.nil?
  puts "ERROR: Application with client_id '#{client_id}' not found!"
  exit
end

puts "Application: #{app.name} (ID: #{app.id})"
puts "Creating #{num_users} test users..."

CSV.open("test_users_with_tokens.csv", "w") do |csv|
  csv << ["email", "username", "password", "access_token", "user_id", "account_id"]
  
  num_users.times do |i|
    begin
      username = "testuser#{(i+1).to_s.rjust(4, '0')}"
      email = "#{username}@test.com"
      password = "TestPass#{i+1}!"
      
      user = User.new(
        email: email,
        password: password,
        password_confirmation: password,
        agreement: true,
        confirmed_at: Time.current,
        approved: true
      )

      user.build_account(
        username: username,
        domain: nil
      )

      user.save!

      token = Doorkeeper::AccessToken.create!(
        application: app,
        resource_owner_id: user.id,
        scopes: 'read write follow',
        expires_in: 2.years.to_i,
        use_refresh_token: true
      )
      
      csv << [email, username, password, token.token, user.id, user.account.id]
      
      puts "Created user #{i+1}/#{num_users}: #{username}" if (i+1) % 50 == 0
      
    rescue => e
      puts "Error creating user #{i+1}: #{e.message}"
      next
    end
  end
end

puts "CSV file created: test_users_with_tokens.csv"